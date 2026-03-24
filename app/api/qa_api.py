# -*- coding: utf-8 -*-
"""
Q&A API
FastAPI endpoint for Q&A queries that includes figure notes
"""

import logging
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel

from app.config import APPDATA_PATH, CACHE_PATH
from app.core.pdf_vector_db import PDFVectorStore
from app.core.rag.embedding import EmbeddingGenerator
from app.core.storage.database import DatabaseManager
from app.core.storage.asset_manager import AssetManager
from app.common.config import cfg
from app.core.utils.logger import setup_logger

logger = setup_logger("QAAPI")

# Initialize database manager
db_manager = DatabaseManager(str(CACHE_PATH))
asset_manager = AssetManager(db_manager)

# Initialize FastAPI app
app = FastAPI(title="Q&A API", version="1.0.0")


# Pydantic models
class QARequest(BaseModel):
    question: str
    top_k: Optional[int] = 5


class FigureResponse(BaseModel):
    asset_id: str
    page_no: int
    image_path: str
    teacher_note: Optional[str] = None


class QAResponse(BaseModel):
    answer: str
    sources: List[Dict]
    figures: List[FigureResponse]


def get_embedding_generator():
    """获取embedding生成器"""
    embedding_type = cfg.get(cfg.rag_embedding_type) if hasattr(cfg, 'rag_embedding_type') else "gemini"
    embedding_model = cfg.get(cfg.rag_embedding_model) if hasattr(cfg, 'rag_embedding_model') else "paraphrase-multilingual-MiniLM-L12-v2"
    
    if embedding_type == "openai":
        api_key = cfg.get(cfg.openai_api_key)
        api_base = cfg.get(cfg.openai_api_base)
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        return EmbeddingGenerator(
            model_type="openai",
            api_key=api_key,
            api_base=api_base,
            model_name=embedding_model
        )
    elif embedding_type == "gemini":
        api_key = cfg.get(cfg.gemini_api_key)
        if not api_key:
            raise ValueError("Gemini API key not configured")
        return EmbeddingGenerator(
            model_type="gemini",
            api_key=api_key,
            api_base=None,
            model_name=embedding_model
        )
    else:
        return EmbeddingGenerator(
            model_type="local",
            model_name=embedding_model
        )


@app.post("/qa", response_model=QAResponse)
async def query_qa(request: QARequest = Body(...)):
    """
    Q&A查询端点，返回答案和相关图片
    
    Args:
        request: 包含question和top_k的请求体
        
    Returns:
        包含answer、sources和figures的响应
    """
    try:
        vector_store_path = str(APPDATA_PATH / "pdf_vector_db")
        
        # 1. 初始化向量数据库
        vector_store = PDFVectorStore(vector_store_path)
        
        # 2. 初始化embedding生成器
        embedding_generator = get_embedding_generator()
        
        # 3. 生成查询embedding
        query_embedding = embedding_generator.generate_embedding(request.question)
        
        # 4. 搜索（增加top_k以包含图片备注）
        search_results = vector_store.search(
            query_embedding=query_embedding,
            n_results=request.top_k * 2  # 增加以包含图片
        )
        
        # 5. 分离文本页面和图片备注
        text_sources = []
        figure_ids = set()
        
        for result in search_results:
            metadata = result.get("metadata", {})
            source = metadata.get("source", "pdf")
            
            if source == "asset_note":
                # 这是图片备注
                asset_id = metadata.get("asset_id", "")
                if asset_id:
                    figure_ids.add(asset_id)
            else:
                # 这是文本页面
                text_sources.append({
                    "pdf_name": metadata.get("pdf_name", "Unknown"),
                    "page": metadata.get("page", 0),
                    "content": result.get("document", ""),
                    "distance": result.get("distance", 0.0)
                })
        
        # 限制文本源数量
        text_sources = text_sources[:request.top_k]
        
        # 6. 获取图片信息
        figures = []
        for asset_id in list(figure_ids)[:5]:  # 最多5个图片
            try:
                asset = asset_manager.get_asset_by_id(asset_id)
                if asset and asset.teacher_note:
                    figures.append(FigureResponse(
                        asset_id=asset.asset_id,
                        page_no=asset.page_no,
                        image_path=asset.image_path,
                        teacher_note=asset.teacher_note
                    ))
            except Exception as e:
                logger.warning(f"Failed to get asset {asset_id}: {e}")
        
        # 7. 构建答案（简化版，实际应该调用LLM）
        # 这里只返回检索到的内容，实际应用中应该调用LLM生成答案
        answer_parts = []
        answer_parts.append("Based on the retrieved documents:\n\n")
        
        for i, source in enumerate(text_sources, 1):
            answer_parts.append(
                f"[{i}] {source['pdf_name']} - Page {source['page']}:\n"
                f"{source['content'][:500]}...\n\n"
            )
        
        if figures:
            answer_parts.append("\nRelevant Figures:\n")
            for fig in figures:
                answer_parts.append(
                    f"- Page {fig.page_no}: {fig.teacher_note} "
                    f"(asset_id={fig.asset_id})\n"
                )
        
        answer = "\n".join(answer_parts)
        
        return QAResponse(
            answer=answer,
            sources=text_sources,
            figures=figures
        )
        
    except Exception as e:
        logger.error(f"Q&A query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
