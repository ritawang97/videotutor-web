# app/core/storage/models.py
from datetime import date, datetime

from sqlalchemy import JSON, Column, Date, DateTime, Index, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ASRCache(Base):
    """语音识别缓存表"""

    __tablename__ = "asr_cache"

    id = Column(Integer, primary_key=True)
    crc32_hex = Column(String(8), nullable=False, index=True)
    asr_type = Column(String(50), nullable=False)  # ASR服务类型
    result_data = Column(JSON, nullable=False)  # ASR结果数据
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_asr_cache_unique", "crc32_hex", "asr_type", unique=True),
    )


class TranslationCache(Base):
    """翻译结果缓存表"""

    __tablename__ = "translation_cache"

    id = Column(Integer, primary_key=True)
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    translator_type = Column(String(50), nullable=False)
    params = Column(JSON)
    content_hash = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("idx_translation_lookup", content_hash, translator_type),)

    def __repr__(self):
        return f"<Translation(id={self.id}, translator={self.translator_type})>"


class LLMCache(Base):
    """LLM调用结果缓存表"""

    __tablename__ = "llm_cache"

    id = Column(Integer, primary_key=True)
    prompt = Column(Text, nullable=False)
    result = Column(Text, nullable=False)
    model_name = Column(String(100), nullable=False)
    params = Column(JSON)
    content_hash = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("idx_llm_lookup", content_hash, model_name),)

    def __repr__(self):
        return f"<LlmResult(id={self.id}, model={self.model_name})>"


class UsageStatistics(Base):
    """使用统计表"""

    __tablename__ = "usage_statistics"

    id = Column(Integer, primary_key=True)
    operation_type = Column(String(50), nullable=False)
    service_name = Column(String(50), nullable=False)
    call_count = Column(Integer, default=0)
    token_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_usage_lookup", operation_type, service_name, unique=True),
    )

    def __repr__(self):
        return f"<UsageStatistics({self.operation_type}:{self.service_name})>"


class DailyServiceUsage(Base):
    """每日服务使用次数表"""

    __tablename__ = "daily_service_usage"

    id = Column(Integer, primary_key=True)
    service_name = Column(String(50), nullable=False)  # 服务名称
    usage_date = Column(Date, nullable=False)  # 使用日期，改用 Date 类型
    usage_count = Column(Integer, default=0)  # 使用次数
    daily_limit = Column(Integer, nullable=False)  # 每日限制次数
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_daily_usage_lookup", service_name, usage_date, unique=True),
    )

    def __repr__(self):
        return f"<DailyServiceUsage(service={self.service_name}, date={self.usage_date}, count={self.usage_count})>"

    def __init__(self, **kwargs):
        """初始化时去除时分秒，只保留日期"""
        if "usage_date" in kwargs:
            if isinstance(kwargs["usage_date"], datetime):
                kwargs["usage_date"] = kwargs["usage_date"].date()
            elif isinstance(kwargs["usage_date"], date):
                pass
        super().__init__(**kwargs)


class QARecord(Base):
    """学生问答记录表"""
    
    __tablename__ = "qa_records"
    
    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)  # 学生问题
    answer = Column(Text, nullable=False)  # AI生成的答案
    teacher_answer = Column(Text, nullable=True)  # 老师修改后的答案（可选）
    related_pages = Column(JSON, nullable=True)  # 相关PDF页面信息（列表）
    llm_service = Column(String(50), nullable=False, default="gemini")  # 使用的LLM服务
    student_name = Column(String(100), nullable=True)  # 学生姓名（可选）
    confidence_score = Column(Integer, nullable=True)  # AI置信度评分（1-5）
    is_reviewed = Column(Integer, default=0)  # 是否已审核（0=未审核，1=已审核）
    reviewed_by = Column(String(100), nullable=True)  # 审核人（老师）
    created_at = Column(DateTime, default=datetime.utcnow)  # 创建时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时间
    reviewed_at = Column(DateTime, nullable=True)  # 审核时间
    
    __table_args__ = (
        Index("idx_qa_created_at", "created_at"),
        Index("idx_qa_reviewed", "is_reviewed"),
    )
    
    def __repr__(self):
        return f"<QARecord(id={self.id}, question={self.question[:50]}..., reviewed={bool(self.is_reviewed)})>"


class Asset(Base):
    """PDF图片资源表"""
    
    __tablename__ = "assets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(String(100), nullable=False, unique=True, index=True)  # UUID或唯一标识符
    doc_id = Column(String(200), nullable=False, index=True)  # PDF文档ID（通常是文件名）
    page_no = Column(Integer, nullable=False, index=True)  # 页码（1-based）
    bbox = Column(JSON, nullable=False)  # 边界框 [x0, y0, x1, y1]
    type = Column(String(50), nullable=False, default="figure")  # 资源类型，默认"figure"
    image_path = Column(String(500), nullable=False)  # 图片文件路径
    teacher_note = Column(Text, nullable=True)  # 教师备注（可选）
    created_at = Column(DateTime, default=datetime.utcnow)  # 创建时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时间
    
    __table_args__ = (
        Index("idx_asset_doc_id", "doc_id"),
        Index("idx_asset_page_no", "page_no"),
        Index("idx_asset_doc_page", "doc_id", "page_no"),
    )
    
    def __repr__(self):
        return f"<Asset(asset_id={self.asset_id}, doc_id={self.doc_id}, page={self.page_no}, type={self.type})>"
