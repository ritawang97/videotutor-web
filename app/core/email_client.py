# -*- coding: utf-8 -*-
"""
Email Client Module
Handles sending emails via SMTP
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parseaddr, getaddresses
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailClient:
    """Email client for sending emails via SMTP"""
    
    def __init__(self, smtp_server: str, smtp_port: int, email: str, password: str, use_tls: bool = True):
        """
        Initialize email client
        
        Args:
            smtp_server: SMTP server address (e.g., smtp-mail.outlook.com)
            smtp_port: SMTP port (587 for TLS, 465 for SSL)
            email: Sender email address
            password: Email password or app password
            use_tls: Whether to use TLS (True for port 587, False for port 465)
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email = email
        self.password = password
        self.use_tls = use_tls
    
    def send_pdf_qa_email(
        self,
        recipient: str,
        question: str,
        pages: List[Dict],
        answer: str,
        llm_service: str = "gemini"
    ) -> bool:
        """
        Send PDF Q&A email with question, pages, content, and answer
        
        Args:
            recipient: Recipient email address
            question: User's question
            pages: List of relevant PDF pages (each dict contains pdf_name, page, content)
            answer: LLM chatbot answer
            llm_service: LLM service used (e.g., "gemini", "openai")
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Build email content
            subject = f"PDF Q&A Result - {question[:50]}..."
            
            # Build HTML email body
            html_body = self._build_html_email(question, pages, answer, llm_service)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email
            msg['To'] = recipient
            msg['Subject'] = subject
            
            # Add HTML content
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Send email
            return self._send_email(msg)
            
        except Exception as e:
            logger.error(f"Failed to send PDF Q&A email: {e}", exc_info=True)
            raise
    
    def _build_html_email(
        self,
        question: str,
        pages: List[Dict],
        answer: str,
        llm_service: str
    ) -> str:
        """Build HTML email content"""
        
        # Build pages section
        pages_html = ""
        for i, page in enumerate(pages, 1):
            pdf_name = page.get("pdf_name", "Unknown")
            page_num = page.get("page", 0)
            content = page.get("content", "")
            
            # Truncate long content
            content_preview = content[:1000] + "..." if len(content) > 1000 else content
            
            pages_html += f"""
            <div style="margin: 15px 0; padding: 10px; background-color: #f5f5f5; border-left: 4px solid #4a90e2;">
                <h4 style="margin: 0 0 10px 0; color: #333;">Document {i}: {pdf_name} - Page {page_num}</h4>
                <pre style="white-space: pre-wrap; word-wrap: break-word; font-family: Arial, sans-serif; font-size: 12px; color: #666; margin: 0;">{content_preview}</pre>
            </div>
            """
        
        # Build HTML template
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background-color: #4a90e2;
                    color: white;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .section {{
                    margin: 20px 0;
                    padding: 15px;
                    background-color: #ffffff;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                }}
                .question {{
                    background-color: #fff3cd;
                    border-left: 4px solid #ffc107;
                }}
                .answer {{
                    background-color: #d4edda;
                    border-left: 4px solid #28a745;
                }}
                h2 {{
                    margin-top: 0;
                    color: #4a90e2;
                }}
                h3 {{
                    color: #666;
                    border-bottom: 2px solid #eee;
                    padding-bottom: 5px;
                }}
                pre {{
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }}
                .metadata {{
                    font-size: 11px;
                    color: #888;
                    margin-top: 10px;
                    padding-top: 10px;
                    border-top: 1px solid #eee;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1 style="margin: 0;">📄 PDF Q&A Result</h1>
                <p style="margin: 5px 0 0 0;">Generated by VideoCaptioner PDF Vector Database</p>
            </div>
            
            <div class="section question">
                <h2>❓ Your Question</h2>
                <p style="font-size: 16px; font-weight: bold;">{question}</p>
            </div>
            
            <div class="section">
                <h2>📄 Related PDF Pages ({len(pages)} pages)</h2>
                {pages_html}
            </div>
            
            <div class="section answer">
                <h2>🤖 Chatbot Answer ({llm_service.upper()})</h2>
                <pre style="white-space: pre-wrap; word-wrap: break-word; font-family: Arial, sans-serif; font-size: 14px;">{answer}</pre>
            </div>
            
            <div class="metadata">
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>LLM Service: {llm_service.upper()}</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _send_email(self, msg: MIMEMultipart) -> bool:
        """Send email via SMTP"""
        try:
            if self.use_tls:
                # Use TLS (for port 587)
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                # Use SSL (for port 465)
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            
            server.login(self.email, self.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent successfully to {msg['To']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            raise
    
    def reply_pdf_qa_email(
        self,
        original_msg,
        question: str,
        pages: List[Dict],
        answer: str,
        llm_service: str = "gemini"
    ) -> bool:
        """
        Reply to an email with PDF Q&A results
        
        Args:
            original_msg: Original email message object
            question: User's question
            pages: List of relevant PDF pages
            answer: LLM chatbot answer
            llm_service: LLM service used
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Build email content
            subject = f"Re: {original_msg.get('Subject', 'PDF Q&A Result')}"
            if not subject.startswith("Re:"):
                subject = f"Re: {subject}"
            
            # Build HTML email body
            html_body = self._build_html_email(question, pages, answer, llm_service)
            
            # Create reply message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email
            
            # Extract recipient email address from From header
            # Handle encoded headers like: =?utf-8?B?UVHpgq7nrrHlm6LpmJ8==?= <10000@qq.com>
            from_header = original_msg.get('From', '')
            if from_header:
                # Parse the From header to extract email address
                # parseaddr returns (display_name, email_address)
                _, recipient_email = parseaddr(from_header)
                if not recipient_email:
                    # Fallback: try to extract email from the header string
                    # Look for email pattern: <email@domain.com>
                    import re
                    email_match = re.search(r'<([^>]+@[^>]+)>', from_header)
                    if email_match:
                        recipient_email = email_match.group(1)
                    else:
                        # Last resort: use the whole header if it looks like an email
                        recipient_email = from_header.strip()
            else:
                recipient_email = ''
            
            if not recipient_email:
                raise ValueError("Cannot extract recipient email address from original email")
            
            msg['To'] = recipient_email
            msg['Subject'] = subject
            msg['In-Reply-To'] = original_msg.get('Message-ID', '')
            msg['References'] = original_msg.get('Message-ID', '')
            
            # Add HTML content
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Send email
            return self._send_email(msg)
            
        except Exception as e:
            logger.error(f"Failed to reply PDF Q&A email: {e}", exc_info=True)
            raise
    
    @staticmethod
    def get_outlook_smtp_config(email: str, password: str):
        """
        Get Outlook SMTP configuration
        
        Args:
            email: Outlook email address
            password: Email password or app password
            
        Returns:
            EmailClient instance configured for Outlook
        """
        return EmailClient(
            smtp_server="smtp-mail.outlook.com",
            smtp_port=587,
            email=email,
            password=password,
            use_tls=True
        )
    
    @staticmethod
    def get_gmail_smtp_config(email: str, password: str):
        """
        Get Gmail SMTP configuration
        
        Args:
            email: Gmail address
            password: Email password or app password
            
        Returns:
            EmailClient instance configured for Gmail
        """
        return EmailClient(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            email=email,
            password=password,
            use_tls=True
        )
    
    @staticmethod
    def get_qq_smtp_config(email: str, password: str):
        """
        Get QQ Mail SMTP configuration
        
        Args:
            email: QQ Mail address
            password: Email authorization code (授权码)
            
        Returns:
            EmailClient instance configured for QQ Mail
        """
        return EmailClient(
            smtp_server="smtp.qq.com",
            smtp_port=587,
            email=email,
            password=password,
            use_tls=True
        )