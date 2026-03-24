# -*- coding: utf-8 -*-
"""
PDF向量数据库处理线程
"""

import logging
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal

from app.core.pdf_vector_db import PDFParser, PDFVectorStore
from app.core.pdf_vector_db.figure_extractor import extract_figures_from_pdf
from app.core.rag.embedding import EmbeddingGenerator
from app.common.config import cfg
from app.core.utils.logger import setup_logger
from app.config import APPDATA_PATH
from app.core.storage.database import DatabaseManager
from app.core.storage.asset_manager import AssetManager

logger = setup_logger("PDFVectorDBThread")


class PDFVectorizationThread(QThread):
    """PDF向量化处理线程"""
    
    progress = pyqtSignal(str)  # 进度信息
    finished = pyqtSignal(bool, str)  # 完成信号：success, message
    error = pyqtSignal(str)  # 错误信息
    
    def __init__(self, pdf_path: str, vector_store_path: str, extract_figures: bool = True):
        """
        初始化线程
        
        Args:
            pdf_path: PDF文件路径
            vector_store_path: 向量数据库存储路径
            extract_figures: 是否提取图片（默认True）
        """
        super().__init__()
        self.pdf_path = Path(pdf_path)
        self.vector_store_path = vector_store_path
        self.extract_figures = extract_figures
        self.is_running = True
    
    def run(self):
        """执行PDF向量化处理"""
        try:
            # 1. 解析PDF
            self.progress.emit("Parsing PDF file...")
            parser = PDFParser()
            pages = parser.parse_pdf(self.pdf_path)
            
            if not pages:
                self.error.emit("No pages found in PDF")
                return
            
            # 过滤空页
            valid_pages = [p for p in pages if not p.get("is_empty", False)]
            if not valid_pages:
                self.error.emit("No valid pages found in PDF (all pages are empty)")
                return
            
            self.progress.emit(f"Parsed {len(valid_pages)} valid pages from {len(pages)} total pages")
            
            if not self.is_running:
                return
            
            # 2. 初始化向量数据库
            self.progress.emit("Initializing vector database...")
            vector_store = PDFVectorStore(self.vector_store_path)
            
            if not self.is_running:
                return
            
            # 3. 初始化embedding生成器
            self.progress.emit("Initializing embedding model...")
            embedding_type = cfg.get(cfg.rag_embedding_type) if hasattr(cfg, 'rag_embedding_type') else "gemini"
            embedding_model = cfg.get(cfg.rag_embedding_model) if hasattr(cfg, 'rag_embedding_model') else "gemini-embedding-001"
            
            if embedding_type == "openai":
                api_key = cfg.get(cfg.openai_api_key)
                api_base = cfg.get(cfg.openai_api_base)
                if not api_key:
                    self.error.emit("OpenAI API key not configured. Please configure it in settings.")
                    return
                embedding_generator = EmbeddingGenerator(
                    model_type="openai",
                    api_key=api_key,
                    api_base=api_base,
                    model_name=embedding_model
                )
            elif embedding_type == "gemini":
                api_key = cfg.get(cfg.gemini_api_key)
                if not api_key or not api_key.strip():
                    self.error.emit("Gemini API key not configured. Please configure it in settings.")
                    return
                # 确保API key没有多余空格
                api_key = api_key.strip()
                embedding_generator = EmbeddingGenerator(
                    model_type="gemini",
                    api_key=api_key,
                    api_base=None,  # Gemini不需要base_url
                    model_name=embedding_model
                )
            else:
                embedding_generator = EmbeddingGenerator(
                    model_type="local",
                    model_name=embedding_model
                )
            
            if not self.is_running:
                return
            
            # 4. 生成embeddings
            self.progress.emit("Generating embeddings...")
            texts = [page["text"] for page in valid_pages]
            
            # 批量生成embeddings
            batch_size = 50
            all_embeddings = []
            total_batches = (len(texts) + batch_size - 1) // batch_size
            
            try:
                for i in range(0, len(texts), batch_size):
                    if not self.is_running:
                        return
                    
                    batch_texts = texts[i:i + batch_size]
                    batch_num = i // batch_size + 1
                    self.progress.emit(f"Generating embeddings: batch {batch_num}/{total_batches}...")
                    
                    try:
                        batch_embeddings = embedding_generator.generate_embeddings(batch_texts)
                        all_embeddings.extend(batch_embeddings)
                    except Exception as e:
                        error_msg = str(e)
                        # 提供更详细的错误信息
                        if "api" in error_msg.lower() or "key" in error_msg.lower() or "unauthorized" in error_msg.lower():
                            detailed_error = (
                                f"API调用失败: {error_msg}\n\n"
                                f"可能的解决方案：\n"
                                f"1. 检查OpenAI API Key是否正确配置\n"
                                f"2. 检查API Key是否有足够的额度\n"
                                f"3. 检查网络连接是否正常\n"
                                f"4. 或者切换到本地embedding模型（在设置中配置）"
                            )
                        else:
                            detailed_error = f"生成embedding失败: {error_msg}"
                        self.error.emit(detailed_error)
                        return
            except Exception as e:
                error_msg = str(e)
                detailed_error = f"生成embedding时发生错误: {error_msg}"
                self.error.emit(detailed_error)
                return
            
            if not self.is_running:
                return
            
            # 5. 存储到向量数据库
            self.progress.emit("Storing vectors to database...")
            pdf_name = self.pdf_path.stem  # 文件名（不含扩展名）
            vector_store.add_pdf_pages(
                pdf_name=pdf_name,
                pages=valid_pages,
                embeddings=all_embeddings,
                skip_empty=True
            )
            
            # 6. 提取图片（如果启用）
            if self.extract_figures:
                try:
                    self.progress.emit("Extracting figures from PDF...")
                    assets_base_dir = APPDATA_PATH / "assets"
                    assets = extract_figures_from_pdf(
                        pdf_path=self.pdf_path,
                        doc_id=pdf_name,
                        assets_base_dir=assets_base_dir
                    )
                    
                    if assets:
                        # 保存资产到数据库
                        self.progress.emit(f"Saving {len(assets)} assets to database...")
                        db_manager = DatabaseManager(str(APPDATA_PATH / "cache"))
                        asset_manager = AssetManager(db_manager)
                        
                        assets_data = [
                            {
                                "asset_id": a.asset_id,
                                "doc_id": a.doc_id,
                                "page_no": a.page_no,
                                "bbox": a.bbox,
                                "type": a.type,
                                "image_path": a.image_path,
                                "teacher_note": a.teacher_note
                            }
                            for a in assets
                        ]
                        asset_manager.create_assets_batch(assets_data)
                        logger.info(f"Extracted and saved {len(assets)} assets from {pdf_name}")
                except Exception as e:
                    logger.warning(f"Failed to extract figures from PDF: {e}", exc_info=True)
                    # 不中断主流程，只记录警告
            
            # 7. 完成
            info = vector_store.get_collection_info()
            total_count = info.get("count", 0)
            pdf_count = info.get("pdf_count", 0)
            
            message = f"Successfully processed {len(valid_pages)} pages. Total vectors in database: {total_count} (from {pdf_count} PDFs)"
            self.finished.emit(True, message)
            
        except Exception as e:
            logger.error(f"PDF vectorization failed: {e}", exc_info=True)
            self.error.emit(f"Processing failed: {str(e)}")
    
    def stop(self):
        """停止处理"""
        self.is_running = False
        self.terminate()
