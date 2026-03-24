# -*- coding: utf-8 -*-
"""
Email发送线程
处理邮件发送的异步任务
"""
import logging
from PyQt5.QtCore import QThread, pyqtSignal
from typing import List, Dict
from app.core.email_client import EmailClient

logger = logging.getLogger(__name__)


class EmailSendThread(QThread):
    """邮件发送线程"""
    
    progress = pyqtSignal(str)  # 进度信息
    success = pyqtSignal(str)  # 成功信号（返回收件人地址）
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        email: str,
        password: str,
        use_tls: bool,
        recipient: str,
        question: str,
        pages: List[Dict],
        answer: str,
        llm_service: str = "gemini"
    ):
        """
        初始化邮件发送线程
        
        Args:
            smtp_server: SMTP服务器地址
            smtp_port: SMTP端口
            email: 发件人邮箱
            password: 邮箱密码
            use_tls: 是否使用TLS
            recipient: 收件人邮箱
            question: 用户问题
            pages: 相关PDF页面列表
            answer: Chatbot回答
            llm_service: LLM服务名称
        """
        super().__init__()
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email = email
        self.password = password
        self.use_tls = use_tls
        self.recipient = recipient
        self.question = question
        self.pages = pages
        self.answer = answer
        self.llm_service = llm_service
    
    def run(self):
        """执行邮件发送任务"""
        try:
            self.progress.emit("Initializing email client...")
            
            # 创建邮件客户端
            email_client = EmailClient(
                smtp_server=self.smtp_server,
                smtp_port=self.smtp_port,
                email=self.email,
                password=self.password,
                use_tls=self.use_tls
            )
            
            self.progress.emit("Sending email...")
            
            # 发送邮件
            email_client.send_pdf_qa_email(
                recipient=self.recipient,
                question=self.question,
                pages=self.pages,
                answer=self.answer,
                llm_service=self.llm_service
            )
            
            self.progress.emit(f"Email sent successfully to {self.recipient}")
            self.success.emit(self.recipient)
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            self.error.emit(str(e))