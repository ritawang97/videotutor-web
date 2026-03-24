# app/core/storage/database.py
import logging
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from .constants import CACHE_CONFIG
from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理类，负责数据库连接和会话管理"""

    def __init__(self, app_data_path: str):
        self.db_path = os.path.join(app_data_path, CACHE_CONFIG["db_filename"])
        self.db_url = f"sqlite:///{self.db_path}"
        self._engine = None
        self._session_maker = None
        self.init_db()

    def init_db(self):
        """初始化数据库连接和表结构"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._engine = create_engine(
                self.db_url,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                pool_recycle=3600,
            )
            # 确保所有表都被创建，包括QARecord和Asset
            Base.metadata.create_all(self._engine, checkfirst=True)
            
            # 运行迁移（添加缺失的列）
            self._run_migrations()
            
            self._session_maker = sessionmaker(bind=self._engine)
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}", exc_info=True)
            raise

    def close(self):
        """关闭数据库连接"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_maker = None

    @contextmanager
    def get_session(self):
        """获取数据库会话的上下文管理器"""
        if not self._engine or not self._session_maker:
            self.init_db()

        if self._session_maker is None:
            raise RuntimeError("Database session maker not initialized")
        session = self._session_maker()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            session.close()
    
    def _run_migrations(self):
        """运行数据库迁移，添加缺失的列"""
        try:
            inspector = inspect(self._engine)
            
            # 检查qa_records表是否存在
            if inspector.has_table("qa_records"):
                columns = [col["name"] for col in inspector.get_columns("qa_records")]
                
                # 检查并添加confidence_score列
                if "confidence_score" not in columns:
                    logger.info("Adding confidence_score column to qa_records table")
                    with self._engine.connect() as conn:
                        conn.execute(text("ALTER TABLE qa_records ADD COLUMN confidence_score INTEGER"))
                        conn.commit()
                    logger.info("Successfully added confidence_score column")
            
            # 检查assets表是否存在（如果不存在，Base.metadata.create_all会创建它）
            # 这里不需要迁移，因为Asset表是新表
            
        except Exception as e:
            logger.warning(f"Migration failed (this is OK if columns already exist): {e}")
            # 不抛出异常，因为列可能已经存在