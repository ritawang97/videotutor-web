# -*- coding: utf-8 -*-
"""
PDF向量数据库聊天线程
处理PDF查询和LLM聊天
"""
import logging
from PyQt5.QtCore import QThread, pyqtSignal
from typing import List, Dict, Optional
from app.core.pdf_vector_db import PDFVectorStore
from app.core.rag.embedding import EmbeddingGenerator
from app.common.config import cfg
from app.core.entities import LLMServiceEnum
from app.config import APPDATA_PATH, CACHE_PATH
from app.core.storage.database import DatabaseManager
from app.core.storage.asset_manager import AssetManager
import openai

logger = logging.getLogger(__name__)


class PDFQueryThread(QThread):
    """PDF查询线程 - 检索相关PDF页面"""
    
    progress = pyqtSignal(str)  # 进度信息
    result = pyqtSignal(list)  # 查询结果：相关页面列表
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(self, question: str, vector_store_path: str, top_k: int = 5):
        """
        初始化PDF查询线程
        
        Args:
            question: 用户问题
            vector_store_path: 向量数据库路径
            top_k: 返回top-k个相关页面
        """
        super().__init__()
        self.question = question
        self.vector_store_path = vector_store_path
        self.top_k = top_k
    
    def run(self):
        """执行查询任务"""
        try:
            self.progress.emit("Initializing vector database...")
            
            # 1. 初始化向量数据库
            vector_store = PDFVectorStore(self.vector_store_path)
            
            # 检查是否有数据
            info = vector_store.get_collection_info()
            if info["count"] == 0:
                self.error.emit("No data in vector database. Please upload PDF files first.")
                return
            
            # 2. 初始化embedding生成器
            self.progress.emit("Generating query embedding...")
            embedding_type = cfg.get(cfg.rag_embedding_type) if hasattr(cfg, 'rag_embedding_type') else "local"
            embedding_model = cfg.get(cfg.rag_embedding_model) if hasattr(cfg, 'rag_embedding_model') else "paraphrase-multilingual-MiniLM-L12-v2"
            
            if embedding_type == "openai":
                api_key = cfg.get(cfg.openai_api_key)
                api_base = cfg.get(cfg.openai_api_base)
                if not api_key:
                    self.error.emit("OpenAI API key not configured")
                    return
                embedding_generator = EmbeddingGenerator(
                    model_type="openai",
                    api_key=api_key,
                    api_base=api_base,
                    model_name=embedding_model
                )
            elif embedding_type == "gemini":
                api_key = cfg.get(cfg.gemini_api_key)
                if not api_key:
                    self.error.emit("Gemini API key not configured")
                    return
                embedding_generator = EmbeddingGenerator(
                    model_type="gemini",
                    api_key=api_key,
                    api_base=None,
                    model_name=embedding_model
                )
            else:
                embedding_generator = EmbeddingGenerator(
                    model_type="local",
                    model_name=embedding_model
                )
            
            # 3. 生成查询embedding
            query_embedding = embedding_generator.generate_embedding(self.question)
            
            # 4. 搜索相关页面（包括文本和图片备注）
            self.progress.emit("Searching relevant PDF pages and figures...")
            # 增加top_k以包含图片备注
            search_results = vector_store.search(query_embedding, n_results=self.top_k * 2)
            
            # 5. 分离文本页面和图片备注
            text_pages = []
            figure_notes = []
            
            for result in search_results:
                metadata = result.get("metadata", {})
                source = metadata.get("source", "pdf")
                
                if source == "asset_note":
                    # 这是图片备注
                    asset_id = metadata.get("asset_id", "")
                    doc_id = metadata.get("doc_id", "")
                    page_no = metadata.get("page_no", 0)
                    
                    # 从数据库获取完整的资产信息
                    try:
                        db_manager = DatabaseManager(str(CACHE_PATH))
                        asset_manager = AssetManager(db_manager)
                        asset = asset_manager.get_asset_by_id(asset_id)
                        
                        if asset and asset.teacher_note:
                            figure_notes.append({
                                "asset_id": asset_id,
                                "doc_id": doc_id,
                                "page_no": page_no,
                                "image_path": asset.image_path,
                                "teacher_note": asset.teacher_note,
                                "distance": result.get("distance", 0.0)
                            })
                    except Exception as e:
                        logger.warning(f"Failed to get asset {asset_id}: {e}")
                else:
                    # 这是文本页面
                    text_pages.append({
                        "pdf_name": metadata.get("pdf_name", "Unknown"),
                        "page": metadata.get("page", 0),
                        "content": result.get("document", ""),
                        "distance": result.get("distance", 0.0)
                    })
            
            # 6. 格式化结果（优先文本页面，然后添加图片备注）
            formatted_results = text_pages[:self.top_k]  # 限制文本页面数量
            
            # 添加图片备注（限制数量）
            max_figures = min(3, len(figure_notes))  # 最多3个图片
            for fig in figure_notes[:max_figures]:
                formatted_results.append({
                    "pdf_name": fig["doc_id"],
                    "page": fig["page_no"],
                    "content": f"[Figure Note] {fig['teacher_note']}",
                    "distance": fig["distance"],
                    "is_figure": True,
                    "asset_id": fig["asset_id"],
                    "image_path": fig["image_path"]
                })
            
            # 7. 发送结果
            self.result.emit(formatted_results)
            
        except Exception as e:
            logger.error(f"PDF query failed: {e}", exc_info=True)
            self.error.emit(f"Query failed: {str(e)}")


class PDFChatThread(QThread):
    """PDF聊天线程 - 使用LLM生成回答"""
    
    progress = pyqtSignal(str)  # 进度信息
    result = pyqtSignal(dict)  # 回答结果：包含answer和confidence_score
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(self, question: str, context_pages: List[Dict], llm_service: str = "gemini"):
        """
        初始化PDF聊天线程
        
        Args:
            question: 用户问题
            context_pages: 相关PDF页面列表（包含pdf_name, page, content）
            llm_service: LLM服务类型（"gemini" 或 "openai"）
        """
        super().__init__()
        self.question = question
        self.context_pages = context_pages
        self.llm_service = llm_service
    
    def run(self):
        """执行聊天任务"""
        try:
            self.progress.emit("Building context...")
            
            # 1. 构建上下文
            context_text = self._build_context(self.context_pages)
            
            # 2. 构建提示词
            prompt = self._build_prompt(self.question, context_text)
            
            # 3. 初始化LLM客户端
            self.progress.emit(f"Generating answer using {self.llm_service}...")
            client, model = self._get_llm_client()
            
            if not client or not model:
                self.error.emit(f"{self.llm_service} API key not configured")
                return
            
            # 4. 调用LLM生成回答
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                timeout=60
            )
            
            full_response = response.choices[0].message.content or ""
            
            # 5. 解析答案和置信度
            answer, confidence_score = self._parse_response(full_response)
            
            # 6. 发送结果
            self.result.emit({
                "answer": answer,
                "confidence_score": confidence_score
            })
            
        except Exception as e:
            logger.error(f"PDF chat failed: {e}", exc_info=True)
            self.error.emit(f"Failed to generate answer: {str(e)}")
    
    def _build_context(self, pages: List[Dict]) -> str:
        """构建上下文文本"""
        context_parts = []
        figure_parts = []
        
        for i, page in enumerate(pages, 1):
            pdf_name = page.get("pdf_name", "Unknown")
            page_num = page.get("page", 0)
            content = page.get("content", "")[:1000]  # 限制每页内容长度
            is_figure = page.get("is_figure", False)
            
            if is_figure:
                # 这是图片备注
                asset_id = page.get("asset_id", "")
                figure_parts.append(f"Page {page_num}: {content} (asset_id={asset_id})")
            else:
                # 这是文本页面
                context_parts.append(f"[Document {i}] {pdf_name} - Page {page_num}:\n{content}\n")
        
        # 组合文本和图片备注
        context_text = "\n".join(context_parts)
        
        if figure_parts:
            context_text += "\n\nRelevant Figures:\n" + "\n".join(figure_parts)
        
        return context_text
    
    def _build_prompt(self, question: str, context: str) -> str:
        """构建LLM提示词"""
        prompt = f"""Based on the following PDF document content, answer the user's question in English.

Relevant document content:
{context}

User question: {question}

Please answer the user's question based on the above document content. If there is no relevant information in the documents, please state so clearly. Your answer should be accurate, concise, and well-organized. Please respond in English.

After your answer, please evaluate your confidence in the answer on a scale of 1-5, where:
- 1: Very low confidence - The answer is mostly inferred or guessed
- 2: Low confidence - Some relevant information found, but not very confident
- 3: Medium confidence - Found relevant information, but may need verification
- 4: High confidence - Found good relevant information, quite confident
- 5: Very high confidence - Found exact or very clear relevant information, very confident

Please format your response as follows:
[ANSWER]
Your answer here...

[CONFIDENCE]
Your confidence score (1-5)"""
        return prompt
    
    def _parse_response(self, response: str) -> tuple:
        """
        解析LLM响应，提取答案和置信度评分
        
        Returns:
            (answer: str, confidence_score: int)
        """
        try:
            # 尝试按格式解析
            if "[ANSWER]" in response and "[CONFIDENCE]" in response:
                parts = response.split("[CONFIDENCE]")
                answer = parts[0].replace("[ANSWER]", "").strip()
                confidence_part = parts[1].strip() if len(parts) > 1 else ""
                
                # 提取数字
                import re
                numbers = re.findall(r'\d+', confidence_part)
                if numbers:
                    confidence_score = int(numbers[0])
                    # 确保在1-5范围内
                    confidence_score = max(1, min(5, confidence_score))
                else:
                    confidence_score = 3  # 默认中等置信度
            else:
                # 如果没有按格式返回，尝试从文本中提取数字
                answer = response
                import re
                # 查找可能的置信度评分（如"confidence: 4"或"评分：5"等）
                confidence_patterns = [
                    r'confidence[:\s]+(\d+)',
                    r'置信度[:\s]+(\d+)',
                    r'评分[:\s]+(\d+)',
                    r'score[:\s]+(\d+)',
                ]
                confidence_score = 3  # 默认值
                for pattern in confidence_patterns:
                    match = re.search(pattern, response, re.IGNORECASE)
                    if match:
                        score = int(match.group(1))
                        if 1 <= score <= 5:
                            confidence_score = score
                            break
            
            return answer, confidence_score
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            # 如果解析失败，返回整个响应作为答案，置信度为3
            return response, 3
    
    def _get_llm_client(self):
        """获取LLM客户端"""
        try:
            if self.llm_service == "gemini":
                base_url = cfg.get(cfg.gemini_api_base)
                api_key = cfg.get(cfg.gemini_api_key)
                model = cfg.get(cfg.gemini_model)
            elif self.llm_service == "openai":
                base_url = cfg.get(cfg.openai_api_base)
                api_key = cfg.get(cfg.openai_api_key)
                model = cfg.get(cfg.openai_model)
            else:
                # 默认使用Gemini
                base_url = cfg.get(cfg.gemini_api_base)
                api_key = cfg.get(cfg.gemini_api_key)
                model = cfg.get(cfg.gemini_model)
            
            if not api_key or api_key.strip() == "":
                return None, None
            
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            return client, model
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            return None, None
