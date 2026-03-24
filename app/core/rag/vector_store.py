# -*- coding: utf-8 -*-
"""
向量数据库管理模块
使用ChromaDB作为向量数据库
"""
import logging
import os
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# 可选导入chromadb
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    Settings = None


class VectorStore:
    """向量数据库管理类"""
    
    def __init__(self, persist_directory: str, collection_name: str = "question_bank"):
        """
        初始化向量数据库
        
        Args:
            persist_directory: 持久化目录路径
            collection_name: 集合名称
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb is not installed. "
                "Please install it with: pip install chromadb"
            )
        
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        
        # 确保目录存在
        os.makedirs(persist_directory, exist_ok=True)
        
        # 初始化ChromaDB客户端
        try:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # 获取或创建集合
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "Student question bank with answers"}
            )
            logger.info(f"Vector store initialized at {persist_directory}")
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
    
    def add_documents(self, texts: List[str], metadatas: List[Dict], ids: Optional[List[str]] = None, 
                     embeddings: Optional[List[List[float]]] = None):
        """
        添加文档到向量数据库
        
        Args:
            texts: 文本列表
            metadatas: 元数据列表（每个文档的元数据）
            ids: 文档ID列表（可选）
            embeddings: 预计算的embedding向量（可选）
        """
        try:
            if ids is None:
                ids = [f"doc_{i}" for i in range(len(texts))]
            
            if embeddings:
                # 使用预计算的embeddings
                self.collection.add(
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas,
                    ids=ids
                )
            else:
                # 让ChromaDB自动生成embeddings（需要配置embedding函数）
                self.collection.add(
                    documents=texts,
                    metadatas=metadatas,
                    ids=ids
                )
            logger.info(f"Added {len(texts)} documents to vector store")
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise
    
    def search(self, query_embedding: List[float], n_results: int = 5, 
               filter_dict: Optional[Dict] = None) -> List[Dict]:
        """
        搜索相似文档
        
        Args:
            query_embedding: 查询文本的embedding向量
            n_results: 返回结果数量
            filter_dict: 过滤条件
            
        Returns:
            相似文档列表，每个文档包含：id, document, metadata, distance
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=filter_dict
            )
            
            # 格式化结果
            formatted_results = []
            if results["ids"] and len(results["ids"][0]) > 0:
                for i in range(len(results["ids"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else None
                    })
            
            return formatted_results
        except Exception as e:
            logger.error(f"Failed to search vector store: {e}")
            raise
    
    def delete_collection(self):
        """删除整个集合"""
        try:
            self.client.delete_collection(name=self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise
    
    def get_collection_info(self) -> Dict:
        """获取集合信息"""
        try:
            count = self.collection.count()
            return {
                "name": self.collection_name,
                "count": count,
                "path": self.persist_directory
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {"name": self.collection_name, "count": 0, "path": self.persist_directory}
    
    def reset(self):
        """重置集合（清空所有数据）"""
        try:
            self.delete_collection()
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Student question bank with answers"}
            )
            logger.info("Vector store reset successfully")
        except Exception as e:
            logger.error(f"Failed to reset vector store: {e}")
            raise

