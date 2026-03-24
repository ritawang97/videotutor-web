# -*- coding: utf-8 -*-
"""
RAG引擎：检索增强生成
结合向量检索和LLM生成，为学生问题提供基于题库的准确回答
"""
import logging
from typing import List, Dict, Optional
from .embedding import EmbeddingGenerator
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class RAGEngine:
    """RAG检索增强生成引擎"""
    
    def __init__(self, vector_store: VectorStore, embedding_generator: EmbeddingGenerator,
                 llm_client=None, top_k: int = 5):
        """
        初始化RAG引擎
        
        Args:
            vector_store: 向量数据库实例
            embedding_generator: Embedding生成器
            llm_client: LLM客户端（用于生成回答）
            top_k: 检索top-k个相关文档
        """
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator
        self.llm_client = llm_client
        self.top_k = top_k
    
    def query(self, question: str, use_llm: bool = True) -> Dict:
        """
        查询并生成回答
        
        Args:
            question: 学生问题
            use_llm: 是否使用LLM生成回答（False时只返回检索结果）
            
        Returns:
            包含回答和相关文档的字典
        """
        try:
            # 1. 生成问题的embedding
            question_embedding = self.embedding_generator.generate_embedding(question)
            
            # 2. 向量检索
            retrieved_docs = self.vector_store.search(
                query_embedding=question_embedding,
                n_results=self.top_k
            )
            
            if not retrieved_docs:
                return {
                    "answer": "抱歉，在题库中没有找到相关的问题和答案。",
                    "sources": [],
                    "confidence": 0.0
                }
            
            # 3. 构建上下文
            context = self._build_context(retrieved_docs)
            
            # 4. 生成回答
            if use_llm and self.llm_client:
                answer = self._generate_answer_with_llm(question, context)
            else:
                # 直接返回最相关的答案
                answer = retrieved_docs[0]["metadata"].get("answer", retrieved_docs[0]["document"])
            
            # 5. 计算置信度（基于相似度）
            confidence = self._calculate_confidence(retrieved_docs)
            
            return {
                "answer": answer,
                "sources": retrieved_docs,
                "context": context,
                "confidence": confidence
            }
        except Exception as e:
            logger.error(f"Failed to query RAG engine: {e}")
            return {
                "answer": f"查询过程中出现错误：{str(e)}",
                "sources": [],
                "confidence": 0.0
            }
    
    def _build_context(self, retrieved_docs: List[Dict]) -> str:
        """构建检索到的文档上下文"""
        context_parts = []
        for i, doc in enumerate(retrieved_docs, 1):
            doc_text = doc["document"]
            metadata = doc.get("metadata", {})
            question = metadata.get("question", "")
            answer = metadata.get("answer", "")
            
            if question and answer:
                context_parts.append(f"参考问题{i}：{question}\n参考答案{i}：{answer}")
            else:
                context_parts.append(f"参考内容{i}：{doc_text}")
        
        return "\n\n".join(context_parts)
    
    def _generate_answer_with_llm(self, question: str, context: str) -> str:
        """使用LLM基于上下文生成回答"""
        if not self.llm_client:
            return "LLM客户端未配置"
        
        prompt = f"""你是一个智能教学助手，需要根据题库中的标准答案来回答学生的问题。

学生问题：{question}

题库中的相关内容：
{context}

请基于上述题库内容，为学生提供一个准确、清晰的回答。要求：
1. 回答要准确，基于题库中的标准答案
2. 语言要清晰易懂，适合学生理解
3. 如果题库中没有完全匹配的内容，可以基于相关内容进行合理推断
4. 回答要简洁，重点突出

回答："""
        
        try:
            response = self.llm_client.generate(prompt)
            return response
        except Exception as e:
            logger.error(f"Failed to generate answer with LLM: {e}")
            # 如果LLM失败，返回最相关的答案
            return "生成回答时出现错误，以下是题库中最相关的答案：\n\n" + context.split("\n\n")[0] if context else ""
    
    def _calculate_confidence(self, retrieved_docs: List[Dict]) -> float:
        """计算回答的置信度（基于检索文档的相似度）"""
        if not retrieved_docs:
            return 0.0
        
        # 使用第一个文档的距离作为置信度指标
        # 距离越小，置信度越高
        first_distance = retrieved_docs[0].get("distance", 1.0)
        
        # 将距离转换为置信度（假设使用余弦相似度，距离范围0-2）
        # 余弦相似度 = 1 - 距离/2
        confidence = max(0.0, min(1.0, 1.0 - first_distance / 2.0))
        
        return confidence


