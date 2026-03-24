# -*- coding: utf-8 -*-
"""
Email Bot Thread
Automatically processes incoming emails, queries PDF database, and replies with answers
"""
import logging
import time
from PyQt5.QtCore import QThread, pyqtSignal
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.core.email_receiver import EmailReceiver
from app.core.email_client import EmailClient
from app.core.pdf_vector_db import PDFVectorStore
from app.core.rag.embedding import EmbeddingGenerator
from app.common.config import cfg
import openai

logger = logging.getLogger(__name__)


class EmailBotThread(QThread):
    """Email bot thread - automatically processes emails and replies"""
    
    progress = pyqtSignal(str)  # Progress information
    new_email = pyqtSignal(dict)  # New email received signal
    reply_sent = pyqtSignal(str)  # Reply sent signal (email address)
    error = pyqtSignal(str)  # Error signal
    
    def __init__(
        self,
        vector_store_path: str,
        imap_server: str,
        imap_port: int,
        bot_email: str,
        bot_password: str,
        smtp_server: str,
        smtp_port: int,
        check_interval: int = 60,
        llm_service: str = "gemini"
    ):
        """
        Initialize email bot thread
        
        Args:
            vector_store_path: Path to PDF vector database
            imap_server: IMAP server address
            imap_port: IMAP port
            bot_email: Bot email address
            bot_password: Bot email password
            smtp_server: SMTP server address
            smtp_port: SMTP port
            check_interval: Email check interval in seconds
            llm_service: LLM service to use ("gemini" or "openai")
        """
        super().__init__()
        self.vector_store_path = vector_store_path
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.bot_email = bot_email
        self.bot_password = bot_password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.check_interval = check_interval
        self.llm_service = llm_service
        self.is_running = False
        self.processed_email_ids = set()  # Track processed emails to avoid duplicates
    
    def run(self):
        """Run email bot - continuously check for new emails"""
        self.is_running = True
        self.progress.emit("Email bot started. Checking for new emails...")
        
        # Check if OAuth is enabled
        from app.common.config import cfg
        use_oauth = cfg.get(cfg.email_use_oauth) if hasattr(cfg, 'email_use_oauth') else False
        
        # Get OAuth token if using OAuth
        oauth_token = None
        if use_oauth:
            from app.core.gmail_oauth import get_gmail_oauth_token
            oauth_token = get_gmail_oauth_token(self.bot_email)
            if not oauth_token:
                self.error.emit(
                    "OAuth token not available. Please login with browser first.\n"
                    "Click '🔐 Login with Browser (OAuth)' button."
                )
                self.is_running = False
                return
        
        # Initialize email receiver
        email_receiver = EmailReceiver(
            imap_server=self.imap_server,
            imap_port=self.imap_port,
            email=self.bot_email,
            password=self.bot_password if not use_oauth else None,
            use_ssl=True,
            use_oauth=use_oauth,
            oauth_token=oauth_token
        )
        
        try:
            if not email_receiver.connect():
                self.error.emit("Failed to connect to IMAP server. Please check your email configuration and network connection.")
                self.is_running = False
                return
        except Exception as e:
            error_msg = str(e)
            self.error.emit(f"IMAP Connection Error:\n{error_msg}")
            self.is_running = False
            return
        
        # Initialize email sender (auto-detect or use configured)
        # Check if it's Gmail or Outlook
        email_domain = self.bot_email.split('@')[1].lower() if '@' in self.bot_email else ''
        if 'outlook.com' in email_domain or 'hotmail.com' in email_domain or 'live.com' in email_domain:
            email_sender = EmailClient.get_outlook_smtp_config(
                email=self.bot_email,
                password=self.bot_password if not use_oauth else None
            )
        else:
            # Default to Gmail or use generic SMTP
            email_sender = EmailClient(
                smtp_server=self.smtp_server,
                smtp_port=self.smtp_port,
                email=self.bot_email,
                password=self.bot_password if not use_oauth else None,
                use_tls=True
            )
        
        # Initialize vector store
        try:
            vector_store = PDFVectorStore(self.vector_store_path)
            info = vector_store.get_collection_info()
            if info["count"] == 0:
                self.progress.emit("Warning: No data in vector database")
        except Exception as e:
            self.error.emit(f"Failed to initialize vector store: {str(e)}")
            email_receiver.disconnect()
            self.is_running = False
            return
        
        # Initialize embedding generator
        embedding_generator = self._init_embedding_generator()
        if not embedding_generator:
            embedding_type = cfg.get(cfg.rag_embedding_type) if hasattr(cfg, 'rag_embedding_type') else "local"
            if embedding_type == "local":
                error_msg = (
                    "Failed to initialize embedding generator.\n\n"
                    "You are using local embedding model, but 'sentence-transformers' is not installed.\n\n"
                    "Please install it with:\n"
                    "  pip install sentence-transformers\n\n"
                    "Or switch to OpenAI/Gemini embedding in Settings."
                )
            elif embedding_type == "openai":
                error_msg = (
                    "Failed to initialize embedding generator.\n\n"
                    "OpenAI API key is not configured.\n\n"
                    "Please configure OpenAI API key in Settings."
                )
            elif embedding_type == "gemini":
                error_msg = (
                    "Failed to initialize embedding generator.\n\n"
                    "Gemini API key is not configured.\n\n"
                    "Please configure Gemini API key in Settings."
                )
            else:
                error_msg = f"Failed to initialize embedding generator (type: {embedding_type})"
            
            self.error.emit(error_msg)
            email_receiver.disconnect()
            self.is_running = False
            return
        
        # Main loop
        while self.is_running:
            try:
                # Check for new emails
                self.progress.emit("Checking for new emails...")
                unread_emails = email_receiver.get_unread_emails()
                
                for email_data in unread_emails:
                    email_id = email_data.get("id")
                    
                    # Skip if already processed
                    if email_id in self.processed_email_ids:
                        continue
                    
                    # Process email
                    self.progress.emit(f"Processing email from {email_data.get('from', 'Unknown')}...")
                    self.new_email.emit(email_data)
                    
                    # Extract question from email body
                    question = self._extract_question(email_data.get("body", ""))
                    if not question:
                        self.progress.emit("No question found in email, skipping...")
                        email_receiver.mark_as_read(email_id)
                        self.processed_email_ids.add(email_id)
                        continue
                    
                    # Query PDF database
                    self.progress.emit(f"Searching PDF database for: {question[:50]}...")
                    pages = self._query_pdf_database(
                        question=question,
                        vector_store=vector_store,
                        embedding_generator=embedding_generator
                    )
                    
                    if not pages:
                        # No relevant pages found
                        answer = "I couldn't find any relevant information in the PDF database for your question."
                        self.progress.emit("No relevant pages found")
                    else:
                        # Generate answer using LLM
                        self.progress.emit(f"Generating answer using {self.llm_service}...")
                        answer = self._generate_answer(
                            question=question,
                            pages=pages
                        )
                    
                    # Send reply
                    self.progress.emit("Sending reply email...")
                    try:
                        original_msg = email_data.get("message")
                        email_sender.reply_pdf_qa_email(
                            original_msg=original_msg,
                            question=question,
                            pages=pages,
                            answer=answer,
                            llm_service=self.llm_service
                        )
                        self.reply_sent.emit(email_data.get("from", "Unknown"))
                        self.progress.emit(f"Reply sent successfully to {email_data.get('from', 'Unknown')}")
                    except Exception as e:
                        logger.error(f"Failed to send reply: {e}", exc_info=True)
                        self.error.emit(f"Failed to send reply: {str(e)}")
                    
                    # Mark email as read and add to processed set
                    email_receiver.mark_as_read(email_id)
                    self.processed_email_ids.add(email_id)
                
                # Wait before next check
                if self.is_running:
                    time.sleep(self.check_interval)
            
            except Exception as e:
                logger.error(f"Error in email bot loop: {e}", exc_info=True)
                self.error.emit(f"Error: {str(e)}")
                if self.is_running:
                    time.sleep(self.check_interval)
        
        # Cleanup
        email_receiver.disconnect()
        self.progress.emit("Email bot stopped")
    
    def stop(self):
        """Stop email bot"""
        self.is_running = False
        self.progress.emit("Stopping email bot...")
    
    def _init_embedding_generator(self) -> Optional[EmbeddingGenerator]:
        """Initialize embedding generator"""
        try:
            embedding_type = cfg.get(cfg.rag_embedding_type) if hasattr(cfg, 'rag_embedding_type') else "local"
            embedding_model = cfg.get(cfg.rag_embedding_model) if hasattr(cfg, 'rag_embedding_model') else "paraphrase-multilingual-MiniLM-L12-v2"
            
            if embedding_type == "openai":
                api_key = cfg.get(cfg.openai_api_key)
                api_base = cfg.get(cfg.openai_api_base)
                if not api_key:
                    logger.error("OpenAI API key not configured")
                    return None
                return EmbeddingGenerator(
                    model_type="openai",
                    api_key=api_key,
                    api_base=api_base,
                    model_name=embedding_model
                )
            elif embedding_type == "gemini":
                api_key = cfg.get(cfg.gemini_api_key)
                if not api_key:
                    logger.error("Gemini API key not configured")
                    return None
                return EmbeddingGenerator(
                    model_type="gemini",
                    api_key=api_key,
                    api_base=None,
                    model_name=embedding_model
                )
            else:
                # Local model
                return EmbeddingGenerator(
                    model_type="local",
                    model_name=embedding_model
                )
        except ImportError as e:
            error_msg = str(e)
            if "sentence-transformers" in error_msg:
                logger.error(f"Failed to initialize embedding generator: {error_msg}")
                logger.error("Please install sentence-transformers: pip install sentence-transformers")
            else:
                logger.error(f"Failed to initialize embedding generator: {error_msg}")
            return None
        except ValueError as e:
            error_msg = str(e)
            logger.error(f"Failed to initialize embedding generator: {error_msg}")
            return None
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to initialize embedding generator: {error_msg}", exc_info=True)
            return None
    
    def _extract_question(self, email_body: str) -> Optional[str]:
        """Extract question from email body"""
        if not email_body:
            return None
        
        # Clean up email body
        body = email_body.strip()
        
        # Remove common email signatures and quoted text
        lines = body.split('\n')
        question_lines = []
        for line in lines:
            line = line.strip()
            # Skip empty lines, quoted text, and signatures
            if not line:
                continue
            if line.startswith('>') or line.startswith('On ') or line.startswith('From:'):
                break
            if '-----' in line or 'Sent from' in line or 'Best regards' in line:
                break
            question_lines.append(line)
        
        question = '\n'.join(question_lines).strip()
        
        # Return question if it's not empty and has reasonable length
        if question and len(question) > 5:
            return question
        
        return None
    
    def _query_pdf_database(
        self,
        question: str,
        vector_store: PDFVectorStore,
        embedding_generator: EmbeddingGenerator,
        top_k: int = 5
    ) -> List[Dict]:
        """Query PDF database for relevant pages"""
        try:
            # Generate query embedding
            query_embedding = embedding_generator.generate_embedding(question)
            
            # Search for relevant pages
            results = vector_store.search(query_embedding, n_results=top_k)
            
            # Format results
            formatted_results = []
            for result in results:
                metadata = result.get("metadata", {})
                formatted_results.append({
                    "pdf_name": metadata.get("pdf_name", "Unknown"),
                    "page": metadata.get("page", 0),
                    "content": result.get("document", ""),
                    "distance": result.get("distance", 0.0)
                })
            
            return formatted_results
        except Exception as e:
            logger.error(f"Failed to query PDF database: {e}", exc_info=True)
            return []
    
    def _generate_answer(self, question: str, pages: List[Dict]) -> str:
        """Generate answer using LLM"""
        try:
            # Build context
            context_text = self._build_context(pages)
            
            # Build prompt
            prompt = self._build_prompt(question, context_text)
            
            # Get LLM client
            client, model = self._get_llm_client()
            if not client or not model:
                return "Error: LLM API key not configured"
            
            # Call LLM
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                timeout=60
            )
            
            answer = response.choices[0].message.content or "No answer generated"
            return answer
        
        except Exception as e:
            logger.error(f"Failed to generate answer: {e}", exc_info=True)
            return f"Error generating answer: {str(e)}"
    
    def _build_context(self, pages: List[Dict]) -> str:
        """Build context text from pages"""
        context_parts = []
        for i, page in enumerate(pages, 1):
            pdf_name = page.get("pdf_name", "Unknown")
            page_num = page.get("page", 0)
            content = page.get("content", "")[:1000]  # Limit content length
            
            context_parts.append(f"[Document {i}] {pdf_name} - Page {page_num}:\n{content}\n")
        
        return "\n".join(context_parts)
    
    def _build_prompt(self, question: str, context: str) -> str:
        """Build LLM prompt"""
        prompt = f"""Based on the following PDF document content, answer the user's question in English.

Relevant document content:
{context}

User question: {question}

Please answer the user's question based on the above document content. If there is no relevant information in the documents, please state so clearly. Your answer should be accurate, concise, and well-organized. Please respond in English."""
        return prompt
    
    def _get_llm_client(self):
        """Get LLM client"""
        try:
            if self.llm_service == "gemini":
                base_url = cfg.get(cfg.gemini_api_base)
                api_key = cfg.get(cfg.gemini_api_key)
                model = cfg.get(cfg.gemini_model)
            elif self.llm_service == "openai":
                base_url = cfg.get(cfg.openai_api_base)
                api_key = cfg.get(cfg.openai_api_key)
                model = cfg.get(cfg.openai_model)
            else:
                # Default to Gemini
                base_url = cfg.get(cfg.gemini_api_base)
                api_key = cfg.get(cfg.gemini_api_key)
                model = cfg.get(cfg.gemini_model)
            
            if not api_key or api_key.strip() == "":
                return None, None
            
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            return client, model
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            return None, None
