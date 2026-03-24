# -*- coding: utf-8 -*-
"""
Asset Manager
Manages PDF figure assets in the database
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime

from .database import DatabaseManager
from .models import Asset

logger = logging.getLogger(__name__)


class AssetManager:
    """资产管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初始化资产管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
    
    def create_asset(
        self,
        asset_id: str,
        doc_id: str,
        page_no: int,
        bbox: List[float],
        image_path: str,
        type: str = "figure",
        teacher_note: Optional[str] = None
    ) -> Asset:
        """
        创建资产记录
        
        Args:
            asset_id: 资产唯一ID
            doc_id: 文档ID
            page_no: 页码（1-based）
            bbox: 边界框 [x0, y0, x1, y1]
            image_path: 图片文件路径
            type: 资源类型，默认"figure"
            teacher_note: 教师备注（可选）
            
        Returns:
            创建的Asset对象
        """
        try:
            with self.db_manager.get_session() as session:
                # 检查是否已存在
                existing = session.query(Asset).filter(Asset.asset_id == asset_id).first()
                if existing:
                    logger.warning(f"Asset {asset_id} already exists, skipping creation")
                    return existing
                
                asset = Asset(
                    asset_id=asset_id,
                    doc_id=doc_id,
                    page_no=page_no,
                    bbox=bbox,
                    type=type,
                    image_path=image_path,
                    teacher_note=teacher_note
                )
                session.add(asset)
                session.flush()
                logger.info(f"Created asset {asset_id} for doc {doc_id}, page {page_no}")
                return asset
        except Exception as e:
            logger.error(f"Failed to create asset: {e}", exc_info=True)
            raise
    
    def create_assets_batch(self, assets: List[Dict]) -> List[Asset]:
        """
        批量创建资产
        
        Args:
            assets: 资产字典列表，每个字典包含 asset_id, doc_id, page_no, bbox, image_path, type, teacher_note
            
        Returns:
            创建的Asset对象列表
        """
        created = []
        try:
            with self.db_manager.get_session() as session:
                for asset_data in assets:
                    # 检查是否已存在
                    existing = session.query(Asset).filter(
                        Asset.asset_id == asset_data["asset_id"]
                    ).first()
                    if existing:
                        logger.debug(f"Asset {asset_data['asset_id']} already exists, skipping")
                        created.append(existing)
                        continue
                    
                    asset = Asset(
                        asset_id=asset_data["asset_id"],
                        doc_id=asset_data["doc_id"],
                        page_no=asset_data["page_no"],
                        bbox=asset_data["bbox"],
                        type=asset_data.get("type", "figure"),
                        image_path=asset_data["image_path"],
                        teacher_note=asset_data.get("teacher_note")
                    )
                    session.add(asset)
                    created.append(asset)
                
                session.flush()
                logger.info(f"Created {len(created)} assets in batch")
                return created
        except Exception as e:
            logger.error(f"Failed to create assets batch: {e}", exc_info=True)
            raise
    
    def get_asset_by_id(self, asset_id: str) -> Optional[Asset]:
        """
        根据asset_id获取资产
        
        Args:
            asset_id: 资产ID
            
        Returns:
            Asset对象，如果不存在则返回None
        """
        try:
            with self.db_manager.get_session() as session:
                asset = session.query(Asset).filter(Asset.asset_id == asset_id).first()
                if asset:
                    session.expunge(asset)  # 分离对象
                return asset
        except Exception as e:
            logger.error(f"Failed to get asset by ID: {e}", exc_info=True)
            raise
    
    def get_assets_by_doc_id(self, doc_id: str) -> List[Dict]:
        """
        获取文档的所有资产
        
        Args:
            doc_id: 文档ID
            
        Returns:
            资产字典列表（避免会话绑定问题）
        """
        try:
            with self.db_manager.get_session() as session:
                assets = session.query(Asset).filter(Asset.doc_id == doc_id).order_by(
                    Asset.page_no, Asset.id
                ).all()
                
                # 转换为字典
                result = []
                for asset in assets:
                    result.append({
                        "asset_id": asset.asset_id,
                        "doc_id": asset.doc_id,
                        "page_no": asset.page_no,
                        "bbox": asset.bbox,
                        "type": asset.type,
                        "image_path": asset.image_path,
                        "teacher_note": asset.teacher_note,
                        "created_at": asset.created_at,
                        "updated_at": asset.updated_at
                    })
                
                return result
        except Exception as e:
            logger.error(f"Failed to get assets by doc_id: {e}", exc_info=True)
            raise
    
    def update_teacher_note(self, asset_id: str, teacher_note: str) -> bool:
        """
        更新资产的教师备注
        
        Args:
            asset_id: 资产ID
            teacher_note: 教师备注
            
        Returns:
            是否更新成功
        """
        try:
            with self.db_manager.get_session() as session:
                asset = session.query(Asset).filter(Asset.asset_id == asset_id).first()
                if not asset:
                    logger.warning(f"Asset {asset_id} not found")
                    return False
                
                asset.teacher_note = teacher_note
                asset.updated_at = datetime.utcnow()
                session.flush()
                logger.info(f"Updated teacher note for asset {asset_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to update teacher note: {e}", exc_info=True)
            raise
    
    def get_assets_with_notes(self, doc_id: Optional[str] = None) -> List[Dict]:
        """
        获取有教师备注的资产
        
        Args:
            doc_id: 文档ID（可选，如果提供则只返回该文档的资产）
            
        Returns:
            资产字典列表
        """
        try:
            with self.db_manager.get_session() as session:
                query = session.query(Asset).filter(Asset.teacher_note.isnot(None))
                if doc_id:
                    query = query.filter(Asset.doc_id == doc_id)
                
                assets = query.order_by(Asset.doc_id, Asset.page_no).all()
                
                result = []
                for asset in assets:
                    result.append({
                        "asset_id": asset.asset_id,
                        "doc_id": asset.doc_id,
                        "page_no": asset.page_no,
                        "bbox": asset.bbox,
                        "type": asset.type,
                        "image_path": asset.image_path,
                        "teacher_note": asset.teacher_note,
                        "created_at": asset.created_at,
                        "updated_at": asset.updated_at
                    })
                
                return result
        except Exception as e:
            logger.error(f"Failed to get assets with notes: {e}", exc_info=True)
            raise
    
    def delete_asset(self, asset_id: str) -> bool:
        """
        删除资产
        
        Args:
            asset_id: 资产ID
            
        Returns:
            是否删除成功
        """
        try:
            with self.db_manager.get_session() as session:
                asset = session.query(Asset).filter(Asset.asset_id == asset_id).first()
                if not asset:
                    logger.warning(f"Asset {asset_id} not found")
                    return False
                
                session.delete(asset)
                session.flush()
                logger.info(f"Deleted asset {asset_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete asset: {e}", exc_info=True)
            raise
