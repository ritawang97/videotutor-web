# -*- coding: utf-8 -*-
"""
RAG问答系统线程模块
处理题库导入和问答的异步任务
"""
import logging
from PyQt5.QtCore import QThread, pyqtSignal
from pathlib import Path
from app.core.rag.embedding import EmbeddingGenerator
from app.core.rag.vector_store import VectorStore
from app.core.rag.question_bank_processor import QuestionBankProcessor
from app.core.rag.rag_engine import RAGEngine
from app.core.rag.llm_client import RAGLLMClient
from app.common.config import cfg
from app.config import APPDATA_PATH

logger = logging.getLogger(__name__)


class QuestionBankImportThread(QThread):
    """题库导入线程"""
    
    progress = pyqtSignal(str)  # 进度信息
    finished = pyqtSignal(bool, str)  # 完成信号：(成功, 消息)
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(self, file_path: str, vector_store_path: str = None):
        """
        初始化题库导入线程
        
        Args:
            file_path: 题库文件路径
            vector_store_path: 向量数据库存储路径（可选）
        """
        super().__init__()
        self.file_path = file_path
        self.vector_store_path = vector_store_path or str(APPDATA_PATH / "rag_vector_db")
        self.is_running = True
    
    def run(self):
        """执行导入任务"""
        try:
            self.progress.emit("开始加载题库文件...")
            
            # 1. 加载题库
            processor = QuestionBankProcessor()
            questions = processor.load_question_bank(self.file_path)
            
            if not questions:
                self.error.emit("题库文件为空或格式不正确")
                return
            
            self.progress.emit(f"成功加载 {len(questions)} 道题目")
            
            # 2. 准备文档
            self.progress.emit("正在处理题目内容...")
            documents = processor.prepare_documents(questions)
            self.progress.emit(f"生成了 {len(documents)} 个文档块")
            
            # 3. 初始化向量数据库
            self.progress.emit("正在初始化向量数据库...")
            vector_store = VectorStore(
                persist_directory=self.vector_store_path,
                collection_name="question_bank"
            )
            
            # 4. 初始化embedding生成器
            self.progress.emit("正在初始化Embedding模型...")
            embedding_type = cfg.get(cfg.rag_embedding_type)
            embedding_model = cfg.get(cfg.rag_embedding_model)
            
            if embedding_type == "openai":
                api_key = cfg.get(cfg.openai_api_key)
                api_base = cfg.get(cfg.openai_api_base)
                embedding_generator = EmbeddingGenerator(
                    model_type="openai",
                    api_key=api_key,
                    api_base=api_base,
                    model_name=embedding_model
                )
            else:
                embedding_generator = EmbeddingGenerator(
                    model_type="local",
                    model_name=embedding_model
                )
            
            # 5. 生成embeddings并存储
            self.progress.emit("正在生成Embedding向量...")
            batch_size = 50  # 批量处理
            total = len(documents)
            
            for i in range(0, total, batch_size):
                if not self.is_running:
                    self.error.emit("导入已取消")
                    return
                
                batch = documents[i:min(i + batch_size, total)]
                texts = [doc[0] for doc in batch]
                metadatas = [doc[1] for doc in batch]
                ids = [f"doc_{i+j}" for j in range(len(batch))]
                
                # 生成embeddings
                embeddings = embedding_generator.generate_embeddings(texts)
                
                # 存储到向量数据库
                vector_store.add_documents(
                    texts=texts,
                    metadatas=metadatas,
                    ids=ids,
                    embeddings=embeddings
                )
                
                progress_text = f"已处理 {min(i + batch_size, total)}/{total} 个文档"
                self.progress.emit(progress_text)
            
            # 6. 完成
            info = vector_store.get_collection_info()
            self.finished.emit(True, f"成功导入 {len(questions)} 道题目，共 {info['count']} 个文档块")
            
        except Exception as e:
            logger.error(f"Failed to import question bank: {e}")
            self.error.emit(f"导入失败：{str(e)}")
    
    def stop(self):
        """停止处理"""
        self.is_running = False


class RAGQueryThread(QThread):
    """RAG查询线程"""
    
    progress = pyqtSignal(str)  # 进度信息
    result = pyqtSignal(dict)  # 查询结果
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(self, question: str, vector_store_path: str = None, use_llm: bool = True):
        """
        初始化RAG查询线程
        
        Args:
            question: 学生问题
            vector_store_path: 向量数据库路径
            use_llm: 是否使用LLM生成回答
        """
        super().__init__()
        self.question = question
        self.vector_store_path = vector_store_path or str(APPDATA_PATH / "rag_vector_db")
        self.use_llm = use_llm
    
    def run(self):
        """执行查询任务"""
        try:
            self.progress.emit("正在初始化RAG引擎...")
            
            # 1. 初始化向量数据库
            vector_store = VectorStore(
                persist_directory=self.vector_store_path,
                collection_name="question_bank"
            )
            
            # 检查是否有数据
            info = vector_store.get_collection_info()
            if info["count"] == 0:
                self.error.emit("向量数据库中暂无数据，请先导入题库")
                return
            
            # 2. 初始化embedding生成器
            embedding_type = cfg.get(cfg.rag_embedding_type)
            embedding_model = cfg.get(cfg.rag_embedding_model)
            
            if embedding_type == "openai":
                api_key = cfg.get(cfg.openai_api_key)
                api_base = cfg.get(cfg.openai_api_base)
                embedding_generator = EmbeddingGenerator(
                    model_type="openai",
                    api_key=api_key,
                    api_base=api_base,
                    model_name=embedding_model
                )
            elif embedding_type == "gemini":
                api_key = cfg.get(cfg.gemini_api_key)
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
            
            # 3. 初始化LLM客户端（如果需要）
            llm_client = None
            if self.use_llm:
                try:
                    llm_client = RAGLLMClient()
                except Exception as e:
                    logger.warning(f"Failed to initialize LLM client: {e}")
                    self.progress.emit("LLM客户端初始化失败，将使用直接检索模式")
            
            # 4. 初始化RAG引擎
            rag_engine = RAGEngine(
                vector_store=vector_store,
                embedding_generator=embedding_generator,
                llm_client=llm_client,
                top_k=cfg.get(cfg.rag_top_k)
            )
            
            # 5. 执行查询
            self.progress.emit("正在检索相关题目...")
            result = rag_engine.query(question=self.question, use_llm=self.use_llm)
            
            # 6. 发送结果
            self.result.emit(result)
            
        except Exception as e:
            logger.error(f"Failed to query RAG engine: {e}")
            self.error.emit(f"查询失败：{str(e)}")

