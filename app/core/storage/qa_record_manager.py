# -*- coding: utf-8 -*-
"""
Q&A Record Manager
Manages student Q&A records in the database
"""
import logging
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy import desc

from .database import DatabaseManager
from .models import QARecord

logger = logging.getLogger(__name__)


class QARecordManager:
    """问答记录管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初始化问答记录管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
    
    def save_qa_record(
        self,
        question: str,
        answer: str,
        related_pages: Optional[List[Dict]] = None,
        llm_service: str = "gemini",
        student_name: Optional[str] = None,
        confidence_score: Optional[int] = None
    ) -> int:
        """
        保存问答记录
        
        Args:
            question: 学生问题
            answer: AI生成的答案
            related_pages: 相关PDF页面信息
            llm_service: 使用的LLM服务
            student_name: 学生姓名（可选）
            confidence_score: AI置信度评分（1-5，可选）
            
        Returns:
            保存的记录ID
        """
        try:
            with self.db_manager.get_session() as session:
                qa_record = QARecord(
                    question=question,
                    answer=answer,
                    related_pages=related_pages or [],
                    llm_service=llm_service,
                    student_name=student_name,
                    confidence_score=confidence_score,
                    is_reviewed=0
                )
                session.add(qa_record)
                session.flush()
                record_id = qa_record.id
                logger.info(f"Saved Q&A record with ID: {record_id}, confidence: {confidence_score}")
                return record_id
        except Exception as e:
            logger.error(f"Failed to save Q&A record: {e}", exc_info=True)
            raise
    
    def get_all_records(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        reviewed_only: Optional[bool] = None
    ) -> List[Dict]:
        """
        获取所有问答记录
        
        Args:
            limit: 返回记录数量限制
            offset: 偏移量
            reviewed_only: 是否只返回已审核的记录（None=全部）
            
        Returns:
            问答记录字典列表（避免会话绑定问题）
        """
        try:
            with self.db_manager.get_session() as session:
                query = session.query(QARecord)
                
                if reviewed_only is not None:
                    query = query.filter(QARecord.is_reviewed == (1 if reviewed_only else 0))
                
                query = query.order_by(desc(QARecord.created_at))
                
                if limit:
                    query = query.limit(limit).offset(offset)
                
                records = query.all()
                
                # 在会话内提取所有数据，避免会话关闭后访问属性的问题
                result = []
                for record in records:
                    result.append({
                        'id': record.id,
                        'question': record.question,
                        'answer': record.answer,
                        'teacher_answer': record.teacher_answer,
                        'related_pages': record.related_pages,
                        'llm_service': record.llm_service,
                        'student_name': record.student_name,
                        'confidence_score': record.confidence_score,
                        'is_reviewed': record.is_reviewed,
                        'reviewed_by': record.reviewed_by,
                        'created_at': record.created_at,
                        'updated_at': record.updated_at,
                        'reviewed_at': record.reviewed_at,
                    })
                
                return result
        except Exception as e:
            logger.error(f"Failed to get Q&A records: {e}", exc_info=True)
            raise
    
    def get_record_by_id(self, record_id: int) -> Optional[QARecord]:
        """
        根据ID获取问答记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            问答记录，如果不存在则返回None
            注意：返回的对象在会话关闭后可能无法访问属性，建议使用 get_record_dict_by_id
        """
        try:
            with self.db_manager.get_session() as session:
                record = session.query(QARecord).filter(QARecord.id == record_id).first()
                if record:
                    # 使用 expunge 分离对象，使其可以在会话外使用
                    session.expunge(record)
                return record
        except Exception as e:
            logger.error(f"Failed to get Q&A record by ID: {e}", exc_info=True)
            raise
    
    def get_record_dict_by_id(self, record_id: int) -> Optional[Dict]:
        """
        根据ID获取问答记录（返回字典，避免会话绑定问题）
        
        Args:
            record_id: 记录ID
            
        Returns:
            问答记录字典，如果不存在则返回None
        """
        try:
            with self.db_manager.get_session() as session:
                record = session.query(QARecord).filter(QARecord.id == record_id).first()
                if not record:
                    return None
                
                # 在会话内提取所有数据
                return {
                    'id': record.id,
                    'question': record.question,
                    'answer': record.answer,
                    'teacher_answer': record.teacher_answer,
                    'related_pages': record.related_pages,
                    'llm_service': record.llm_service,
                    'student_name': record.student_name,
                    'confidence_score': record.confidence_score,
                    'is_reviewed': record.is_reviewed,
                    'reviewed_by': record.reviewed_by,
                    'created_at': record.created_at,
                    'updated_at': record.updated_at,
                    'reviewed_at': record.reviewed_at,
                }
        except Exception as e:
            logger.error(f"Failed to get Q&A record by ID: {e}", exc_info=True)
            raise
    
    def update_teacher_answer(
        self,
        record_id: int,
        teacher_answer: str,
        reviewed_by: str
    ) -> bool:
        """
        更新老师修改后的答案
        
        Args:
            record_id: 记录ID
            teacher_answer: 老师修改后的答案
            reviewed_by: 审核人（老师姓名）
            
        Returns:
            是否更新成功
        """
        try:
            with self.db_manager.get_session() as session:
                record = session.query(QARecord).filter(QARecord.id == record_id).first()
                if not record:
                    logger.warning(f"Q&A record {record_id} not found")
                    return False
                
                # 更新字段
                record.teacher_answer = teacher_answer
                record.is_reviewed = 1  # 确保是整数类型
                record.reviewed_by = reviewed_by
                record.reviewed_at = datetime.utcnow()
                record.updated_at = datetime.utcnow()
                
                # 显式刷新并提交
                session.flush()
                
                logger.info(f"Updated Q&A record {record_id} with teacher answer by {reviewed_by}")
                return True
        except Exception as e:
            logger.error(f"Failed to update teacher answer: {e}", exc_info=True)
            raise
    
    def delete_record(self, record_id: int) -> bool:
        """
        删除问答记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            是否删除成功
        """
        try:
            with self.db_manager.get_session() as session:
                record = session.query(QARecord).filter(QARecord.id == record_id).first()
                if not record:
                    logger.warning(f"Q&A record {record_id} not found")
                    return False
                
                session.delete(record)
                logger.info(f"Deleted Q&A record {record_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete Q&A record: {e}", exc_info=True)
            raise
    
    def get_statistics(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            包含统计信息的字典
        """
        try:
            with self.db_manager.get_session() as session:
                total = session.query(QARecord).count()
                reviewed = session.query(QARecord).filter(QARecord.is_reviewed == 1).count()
                unreviewed = total - reviewed
                
                return {
                    "total": total,
                    "reviewed": reviewed,
                    "unreviewed": unreviewed
                }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            raise
