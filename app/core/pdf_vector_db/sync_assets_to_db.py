# -*- coding: utf-8 -*-
"""
同步已提取的图片到数据库
用于修复图片已提取但未保存到数据库的情况
"""

import logging
from pathlib import Path
from typing import List

from app.config import APPDATA_PATH, CACHE_PATH
from app.core.storage.database import DatabaseManager
from app.core.storage.asset_manager import AssetManager
from app.core.pdf_vector_db.figure_extractor import AssetCreate, is_meaningful_image

logger = logging.getLogger(__name__)


def sync_existing_assets_to_db():
    """
    扫描assets目录，将已提取但未保存到数据库的图片同步到数据库
    """
    assets_dir = APPDATA_PATH / "assets"
    if not assets_dir.exists():
        logger.warning("Assets directory does not exist")
        return 0
    
    db_manager = DatabaseManager(str(CACHE_PATH))
    asset_manager = AssetManager(db_manager)
    
    synced_count = 0
    
    # 遍历所有文档目录
    for doc_dir in assets_dir.iterdir():
        if not doc_dir.is_dir():
            continue
        
        doc_id = doc_dir.name
        logger.info(f"Processing document: {doc_id}")
        
        # 遍历所有页面目录
        for page_dir in doc_dir.iterdir():
            if not page_dir.is_dir() or not page_dir.name.startswith("page_"):
                continue
            
            # 提取页码
            try:
                page_no = int(page_dir.name.replace("page_", ""))
            except ValueError:
                continue
            
            # 遍历所有图片文件
            image_files = list(page_dir.glob("*.png")) + list(page_dir.glob("*.jpg")) + list(page_dir.glob("*.jpeg"))
            
            for img_idx, image_path in enumerate(sorted(image_files)):
                try:
                    # 检查图片是否有意义（过滤无意义的图片）
                    try:
                        with open(image_path, "rb") as f:
                            image_bytes = f.read()
                        if not is_meaningful_image(image_bytes):
                            logger.debug(
                                f"Skipping meaningless image {image_path} "
                                f"(likely solid color, too small, or unusual shape)"
                            )
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to check image {image_path}: {e}, skipping")
                        continue
                    
                    # 生成asset_id
                    asset_id = f"{doc_id}_page{page_no}_img{img_idx}"
                    
                    # 检查是否已存在
                    existing = asset_manager.get_asset_by_id(asset_id)
                    if existing:
                        logger.debug(f"Asset {asset_id} already exists, skipping")
                        continue
                    
                    # 创建资产记录（使用默认bbox，因为无法从文件获取）
                    # 尝试从PDF获取bbox（如果PDF还在）
                    bbox = [0.0, 0.0, 100.0, 100.0]  # 默认值
                    
                    asset_data = {
                        "asset_id": asset_id,
                        "doc_id": doc_id,
                        "page_no": page_no,
                        "bbox": bbox,
                        "type": "figure",
                        "image_path": str(image_path),
                        "teacher_note": None
                    }
                    
                    asset_manager.create_asset(**asset_data)
                    synced_count += 1
                    logger.info(f"Synced asset: {asset_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to sync asset {image_path}: {e}", exc_info=True)
                    continue
    
    logger.info(f"Synced {synced_count} assets to database")
    return synced_count
