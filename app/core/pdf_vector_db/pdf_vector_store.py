# -*- coding: utf-8 -*-
"""
PDF向量数据库管理模块
基于ChromaDB，专门用于存储PDF页级向量
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from app.core.utils.logger import setup_logger

logger = setup_logger("PDFVectorStore")

# 可选导入chromadb
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    Settings = None


class PDFVectorStore:
    """PDF向量数据库管理类"""
    
    COLLECTION_NAME = "pdf_pages"
    
    def __init__(self, persist_directory: str):
        """
        初始化PDF向量数据库
        
        Args:
            persist_directory: 持久化目录路径
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb is not installed. "
                "Please install it with: pip install chromadb"
            )
        
        self.persist_directory = persist_directory
        
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
                name=self.COLLECTION_NAME,
                metadata={"description": "PDF pages vector database"}
            )
            logger.info(f"PDF vector store initialized at {persist_directory}")
        except Exception as e:
            logger.error(f"Failed to initialize PDF vector store: {e}")
            raise
    
    def add_pdf_pages(self, 
                     pdf_name: str,
                     pages: List[Dict],
                     embeddings: List[List[float]],
                     skip_empty: bool = True):
        """
        添加PDF页面到向量数据库
        
        Args:
            pdf_name: PDF文件名
            pages: 页面列表，每个页面包含 page_number, text, is_empty
            embeddings: 对应的embedding向量列表
            skip_empty: 是否跳过空页
        """
        if len(pages) != len(embeddings):
            raise ValueError(f"Pages count ({len(pages)}) != embeddings count ({len(embeddings)})")
        
        texts = []
        metadatas = []
        ids = []
        
        for i, page in enumerate(pages):
            # 跳过空页
            if skip_empty and page.get("is_empty", False):
                continue
            
            page_number = page["page_number"]
            text = page["text"]
            
            # 构建ID: pdf_name_page_number
            page_id = f"{pdf_name}_page_{page_number}"
            
            texts.append(text)
            metadatas.append({
                "pdf_name": pdf_name,
                "page": page_number,
                "source": "pdf"
            })
            ids.append(page_id)
        
        if not texts:
            logger.warning(f"No valid pages to add for {pdf_name}")
            return
        
        try:
            self.collection.add(
                embeddings=embeddings[:len(texts)],  # 确保长度匹配
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Added {len(texts)} pages from {pdf_name} to vector store")
        except Exception as e:
            logger.error(f"Failed to add PDF pages: {e}")
            raise
    
    def search(self, 
              query_embedding: List[float], 
              n_results: int = 5,
              pdf_filter: Optional[str] = None) -> List[Dict]:
        """
        搜索相似页面
        
        Args:
            query_embedding: 查询文本的embedding向量
            n_results: 返回结果数量
            pdf_filter: 可选，按PDF文件名过滤
            
        Returns:
            相似页面列表，每个页面包含：id, document, metadata, distance
        """
        try:
            where_filter = None
            if pdf_filter:
                where_filter = {"pdf_name": pdf_filter}
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter
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
    
    def get_all_pages(self, pdf_name: Optional[str] = None) -> List[Dict]:
        """
        获取所有页面（或指定PDF的页面）
        
        Args:
            pdf_name: 可选，PDF文件名过滤
            
        Returns:
            页面列表，每个页面包含：id, document, metadata
        """
        try:
            where_filter = None
            if pdf_name:
                where_filter = {"pdf_name": pdf_name}
            
            # 获取所有数据
            results = self.collection.get(where=where_filter)
            
            pages = []
            if results["ids"]:
                for i in range(len(results["ids"])):
                    pages.append({
                        "id": results["ids"][i],
                        "document": results["documents"][i],
                        "metadata": results["metadatas"][i]
                    })
            
            # 按PDF名称和页码排序
            pages.sort(key=lambda x: (
                x["metadata"].get("pdf_name", ""),
                x["metadata"].get("page", 0)
            ))
            
            return pages
        except Exception as e:
            logger.error(f"Failed to get pages: {e}")
            raise
    
    def get_pdf_list(self) -> List[str]:
        """
        获取所有PDF文件名列表
        
        Returns:
            PDF文件名列表（去重）
        """
        try:
            results = self.collection.get()
            pdf_names = set()
            
            if results["metadatas"]:
                for metadata in results["metadatas"]:
                    pdf_name = metadata.get("pdf_name")
                    if pdf_name:
                        pdf_names.add(pdf_name)
            
            return sorted(list(pdf_names))
        except Exception as e:
            logger.error(f"Failed to get PDF list: {e}")
            return []
    
    def get_collection_info(self) -> Dict:
        """
        获取集合信息
        
        Returns:
            包含count、pdf_count等信息的字典
        """
        try:
            count = self.collection.count()
            pdf_list = self.get_pdf_list()
            
            # 统计每个PDF的页数
            pdf_stats = {}
            if pdf_list:
                results = self.collection.get()
                if results["metadatas"]:
                    for metadata in results["metadatas"]:
                        pdf_name = metadata.get("pdf_name")
                        if pdf_name:
                            pdf_stats[pdf_name] = pdf_stats.get(pdf_name, 0) + 1
            
            return {
                "name": self.COLLECTION_NAME,
                "count": count,
                "pdf_count": len(pdf_list),
                "pdf_list": pdf_list,
                "pdf_stats": pdf_stats,
                "path": self.persist_directory
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {
                "name": self.COLLECTION_NAME,
                "count": 0,
                "pdf_count": 0,
                "pdf_list": [],
                "pdf_stats": {},
                "path": self.persist_directory
            }
    
    def delete_pdf(self, pdf_name: str):
        """
        删除指定PDF的所有页面
        
        Args:
            pdf_name: PDF文件名
        """
        try:
            # 获取该PDF的所有ID
            results = self.collection.get(where={"pdf_name": pdf_name})
            if results["ids"]:
                self.collection.delete(ids=results["ids"])
                logger.info(f"Deleted {len(results['ids'])} pages from {pdf_name}")
            else:
                logger.warning(f"No pages found for {pdf_name}")
        except Exception as e:
            logger.error(f"Failed to delete PDF: {e}")
            raise
    
    def reset(self):
        """重置集合（清空所有数据）"""
        try:
            self.client.delete_collection(name=self.COLLECTION_NAME)
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "PDF pages vector database"}
            )
            logger.info("PDF vector store reset successfully")
        except Exception as e:
            logger.error(f"Failed to reset PDF vector store: {e}")
            raise
