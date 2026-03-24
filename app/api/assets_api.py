# -*- coding: utf-8 -*-
"""
Assets API
FastAPI endpoints for managing PDF figure assets
"""

import logging
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel

from app.config import CACHE_PATH, APPDATA_PATH
from app.core.storage.database import DatabaseManager
from app.core.storage.asset_manager import AssetManager
from app.core.rag.embedding import EmbeddingGenerator
from app.core.pdf_vector_db import PDFVectorStore
from app.common.config import cfg
from app.core.utils.logger import setup_logger

logger = setup_logger("AssetsAPI")

# Initialize database manager
db_manager = DatabaseManager(str(CACHE_PATH))
asset_manager = AssetManager(db_manager)

# Initialize FastAPI app
app = FastAPI(title="PDF Assets API", version="1.0.0")


# Pydantic models
class TeacherNoteRequest(BaseModel):
    teacher_note: str


class AssetResponse(BaseModel):
    asset_id: str
    doc_id: str
    page_no: int
    bbox: List[float]
    type: str
    image_path: str
    teacher_note: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def upsert_asset_note_embedding(asset: dict, vector_store_path: str):
    """
    将资产备注的embedding插入到ChromaDB
    
    Args:
        asset: 资产字典，包含 asset_id, doc_id, page_no, teacher_note 等
        vector_store_path: 向量数据库路径
    """
    teacher_note = asset.get("teacher_note")
    if not teacher_note or not teacher_note.strip():
        logger.warning(f"Asset {asset['asset_id']} has no teacher note, skipping embedding")
        return
    
    try:
        # 初始化向量数据库（使用与PDF相同的collection或创建新的）
        vector_store = PDFVectorStore(vector_store_path)
        
        # 初始化embedding生成器
        embedding_type = cfg.get(cfg.rag_embedding_type) if hasattr(cfg, 'rag_embedding_type') else "gemini"
        embedding_model = cfg.get(cfg.rag_embedding_model) if hasattr(cfg, 'rag_embedding_model') else "paraphrase-multilingual-MiniLM-L12-v2"
        
        if embedding_type == "openai":
            api_key = cfg.get(cfg.openai_api_key)
            api_base = cfg.get(cfg.openai_api_base)
            if not api_key:
                logger.error("OpenAI API key not configured")
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
                logger.error("Gemini API key not configured")
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
        
        # 生成embedding
        embedding = embedding_generator.generate_embedding(teacher_note)
        
        # 准备元数据
        metadata = {
            "doc_id": asset["doc_id"],
            "page_no": asset["page_no"],
            "asset_id": asset["asset_id"],
            "type": "figure",
            "source": "asset_note"
        }
        
        # 插入到向量数据库
        # 使用asset_id作为唯一ID
        doc_id = f"asset:{asset['asset_id']}"
        
        # 检查是否已存在，如果存在则更新
        try:
            # ChromaDB的upsert操作（使用add方法，如果ID已存在会自动更新）
            # 先尝试删除旧记录（如果存在）
            try:
                vector_store.collection.delete(ids=[doc_id])
            except:
                pass  # 如果不存在则忽略
            
            # 添加新记录
            vector_store.collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[teacher_note],
                metadatas=[metadata]
            )
            logger.info(f"Upserted embedding for asset {asset['asset_id']}")
        except Exception as e:
            logger.error(f"Failed to upsert embedding: {e}", exc_info=True)
            raise
        
    except Exception as e:
        logger.error(f"Failed to upsert asset note embedding: {e}", exc_info=True)
        raise


@app.post("/assets/{asset_id}/note", response_model=AssetResponse)
async def add_teacher_note(
    asset_id: str,
    request: TeacherNoteRequest = Body(...)
):
    """
    为资产添加或更新教师备注
    
    Args:
        asset_id: 资产ID
        request: 包含teacher_note的请求体
        
    Returns:
        更新后的资产信息
    """
    try:
        # 更新数据库中的备注
        success = asset_manager.update_teacher_note(asset_id, request.teacher_note)
        if not success:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
        # 获取更新后的资产
        asset = asset_manager.get_asset_by_id(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
        # 将备注的embedding插入到向量数据库
        asset_dict = {
            "asset_id": asset.asset_id,
            "doc_id": asset.doc_id,
            "page_no": asset.page_no,
            "teacher_note": asset.teacher_note
        }
        
        vector_store_path = str(APPDATA_PATH / "pdf_vector_db")
        upsert_asset_note_embedding(asset_dict, vector_store_path)
        
        return AssetResponse(
            asset_id=asset.asset_id,
            doc_id=asset.doc_id,
            page_no=asset.page_no,
            bbox=asset.bbox,
            type=asset.type,
            image_path=asset.image_path,
            teacher_note=asset.teacher_note,
            created_at=asset.created_at.isoformat() if asset.created_at else None,
            updated_at=asset.updated_at.isoformat() if asset.updated_at else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add teacher note: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{doc_id}/assets", response_model=List[AssetResponse])
async def get_document_assets(doc_id: str):
    """
    获取文档的所有资产
    
    Args:
        doc_id: 文档ID
        
    Returns:
        资产列表
    """
    try:
        assets = asset_manager.get_assets_by_doc_id(doc_id)
        
        return [
            AssetResponse(
                asset_id=a["asset_id"],
                doc_id=a["doc_id"],
                page_no=a["page_no"],
                bbox=a["bbox"],
                type=a["type"],
                image_path=a["image_path"],
                teacher_note=a.get("teacher_note"),
                created_at=a["created_at"].isoformat() if a.get("created_at") else None,
                updated_at=a["updated_at"].isoformat() if a.get("updated_at") else None
            )
            for a in assets
        ]
    except Exception as e:
        logger.error(f"Failed to get document assets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
