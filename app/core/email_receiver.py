# -*- coding: utf-8 -*-
"""
Email Receiver Module
Handles receiving emails via IMAP
"""
import logging
import imaplib
import email
import base64
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailReceiver:
    """Email receiver for checking and parsing incoming emails via IMAP"""
    
    def __init__(self, imap_server: str, imap_port: int, email: str, password: str = None, 
                 use_ssl: bool = True, use_oauth: bool = False, oauth_token: str = None):
        """
        Initialize email receiver
        
        Args:
            imap_server: IMAP server address (e.g., imap.gmail.com)
            imap_port: IMAP port (993 for SSL, 143 for TLS)
            email: Email address
            password: Email password or app password (required if not using OAuth)
            use_ssl: Whether to use SSL (True for port 993, False for port 143)
            use_oauth: Whether to use OAuth 2.0 authentication
            oauth_token: OAuth token string (required if use_oauth is True)
        """
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.email = email
        self.password = password
        self.use_ssl = use_ssl
        self.use_oauth = use_oauth
        self.oauth_token = oauth_token
        self.mail = None
    
    def connect(self) -> bool:
        """Connect to IMAP server"""
        try:
            logger.info(f"Attempting to connect to IMAP server: {self.imap_server}:{self.imap_port}")
            if self.use_ssl:
                self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:
                self.mail = imaplib.IMAP4(self.imap_server, self.imap_port)
            
            logger.info(f"IMAP connection established, attempting login for: {self.email}")
            
            if self.use_oauth and self.oauth_token:
                # Use OAuth 2.0 authentication
                logger.info("Using OAuth 2.0 authentication")
                # XOAUTH2 requires a function that returns the auth string
                def oauth_handler(response):
                    return self.oauth_token
                self.mail.authenticate('XOAUTH2', oauth_handler)
            else:
                # Use password authentication
                if not self.password:
                    raise Exception("Password required for non-OAuth authentication")
                self.mail.login(self.email, self.password)
            
            logger.info(f"Successfully connected to IMAP server: {self.imap_server}")
            return True
        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            logger.error(f"IMAP authentication error: {error_msg}", exc_info=True)
            # Provide specific error messages for common issues
            if "AUTHENTICATE failed" in error_msg or "LOGIN failed" in error_msg:
                # Provide specific error messages based on email domain
                email_domain = self.email.split('@')[1].lower() if '@' in self.email else ''
                
                if 'outlook.com' in email_domain or 'hotmail.com' in email_domain or 'live.com' in email_domain:
                    raise Exception(
                        f"Outlook authentication failed. Possible causes:\n"
                        f"1. Incorrect email or password\n"
                        f"2. IMAP might be disabled in Outlook settings\n"
                        f"   - Login to https://outlook.live.com/\n"
                        f"   - Go to Settings → Mail → Sync email\n"
                        f"   - Ensure IMAP is enabled\n"
                        f"3. Account might be locked due to multiple failed login attempts\n"
                        f"   - Wait 15-30 minutes and try again\n"
                        f"   - Or visit https://account.microsoft.com/security to check account status\n"
                        f"4. If two-factor authentication is enabled, you may need an app password\n"
                        f"   - Visit https://account.microsoft.com/security\n"
                        f"   - Generate an app password and use it instead of your regular password"
                    )
                elif 'gmail.com' in email_domain:
                    raise Exception(
                        f"Gmail authentication failed. Possible causes:\n"
                        f"1. Incorrect email or password\n"
                        f"2. You need to use an App Password instead of your regular password\n"
                        f"   - Enable 2-Step Verification in your Google Account\n"
                        f"   - Generate an App Password at: https://myaccount.google.com/apppasswords\n"
                        f"3. IMAP access might be disabled in your email settings"
                    )
                else:
                    raise Exception(
                        f"Authentication failed. Possible causes:\n"
                        f"1. Incorrect email or password\n"
                        f"2. IMAP access might be disabled in your email settings\n"
                        f"3. Account might require app-specific password or OAuth"
                    )
            else:
                raise Exception(f"IMAP connection error: {error_msg}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to connect to IMAP server: {error_msg}", exc_info=True)
            # Provide helpful error messages
            if "Connection refused" in error_msg or "timed out" in error_msg.lower():
                raise Exception(
                    f"Connection failed. Possible causes:\n"
                    f"1. Network connection issue\n"
                    f"2. Firewall blocking IMAP port {self.imap_port}\n"
                    f"3. Incorrect IMAP server address: {self.imap_server}\n"
                    f"4. IMAP server is down"
                )
            elif "certificate" in error_msg.lower() or "SSL" in error_msg:
                raise Exception(
                    f"SSL/TLS error: {error_msg}\n"
                    f"Please check your IMAP server SSL configuration."
                )
            else:
                raise Exception(f"IMAP connection error: {error_msg}")
    
    def disconnect(self):
        """Disconnect from IMAP server"""
        try:
            if self.mail:
                self.mail.logout()
                self.mail = None
                logger.info("Disconnected from IMAP server")
        except Exception as e:
            logger.error(f"Error disconnecting from IMAP server: {e}")
    
    def get_unread_emails(self, folder: str = "INBOX", since_date: Optional[datetime] = None) -> List[Dict]:
        """
        Get unread emails from specified folder
        
        Args:
            folder: Email folder (default: "INBOX")
            since_date: Only get emails since this date (optional)
            
        Returns:
            List of email dictionaries containing: id, subject, from_addr, date, body, message
        """
        if not self.mail:
            if not self.connect():
                return []
        
        try:
            # Select folder
            status, messages = self.mail.select(folder)
            if status != "OK":
                logger.error(f"Failed to select folder: {folder}")
                return []
            
            # Search for unread emails
            search_criteria = "UNSEEN"
            if since_date:
                date_str = since_date.strftime("%d-%b-%Y")
                search_criteria = f"UNSEEN SINCE {date_str}"
            
            status, message_ids = self.mail.search(None, search_criteria)
            if status != "OK":
                logger.error("Failed to search emails")
                return []
            
            email_list = []
            message_id_list = message_ids[0].split()
            
            for msg_id in message_id_list:
                try:
                    # Fetch email
                    status, msg_data = self.mail.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue
                    
                    # Parse email
                    email_body = msg_data[0][1]
                    msg = email.message_from_bytes(email_body)
                    
                    # Extract email information
                    email_info = self._parse_email(msg, msg_id.decode())
                    if email_info:
                        email_list.append(email_info)
                
                except Exception as e:
                    logger.error(f"Error parsing email {msg_id}: {e}")
                    continue
            
            return email_list
        
        except Exception as e:
            logger.error(f"Failed to get unread emails: {e}", exc_info=True)
            return []
    
    def mark_as_read(self, msg_id: str, folder: str = "INBOX"):
        """Mark an email as read"""
        try:
            if not self.mail:
                if not self.connect():
                    return False
            
            self.mail.select(folder)
            self.mail.store(msg_id, '+FLAGS', '\\Seen')
            return True
        except Exception as e:
            logger.error(f"Failed to mark email as read: {e}")
            return False
    
    def _parse_email(self, msg: email.message.Message, msg_id: str) -> Optional[Dict]:
        """Parse email message into dictionary"""
        try:
            # Get subject
            subject = self._decode_header(msg.get("Subject", ""))
            
            # Get from address
            from_addr = msg.get("From", "")
            
            # Get date
            date_str = msg.get("Date", "")
            try:
                date = parsedate_to_datetime(date_str) if date_str else datetime.now()
            except:
                date = datetime.now()
            
            # Get message ID
            message_id = msg.get("Message-ID", msg_id)
            
            # Get body
            body = self._get_email_body(msg)
            
            return {
                "id": msg_id,
                "message_id": message_id,
                "subject": subject,
                "from": from_addr,
                "date": date,
                "body": body,
                "message": msg
            }
        except Exception as e:
            logger.error(f"Failed to parse email: {e}")
            return None
    
    def _decode_header(self, header: str) -> str:
        """Decode email header"""
        try:
            decoded_parts = decode_header(header)
            decoded_str = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_str += part.decode(encoding)
                    else:
                        decoded_str += part.decode('utf-8', errors='ignore')
                else:
                    decoded_str += part
            return decoded_str
        except Exception as e:
            logger.error(f"Failed to decode header: {e}")
            return header
    
    def _get_email_body(self, msg: email.message.Message) -> str:
        """Extract email body text"""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                # Get text content
                if content_type == "text/plain" or content_type == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            body += payload.decode(charset, errors='ignore')
                    except Exception as e:
                        logger.error(f"Error decoding email part: {e}")
        else:
            # Single part message
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='ignore')
            except Exception as e:
                logger.error(f"Error decoding email body: {e}")
        
        # Clean HTML tags if present
        if "<html" in body.lower() or "<body" in body.lower():
            import re
            body = re.sub(r'<[^>]+>', '', body)
            body = body.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        
        return body.strip()
    
    @staticmethod
    def get_gmail_imap_config(email: str, password: str):
        """
        Get Gmail IMAP configuration
        
        Args:
            email: Gmail address
            password: Email password or app password
            
        Returns:
            EmailReceiver instance configured for Gmail
        """
        return EmailReceiver(
            imap_server="imap.gmail.com",
            imap_port=993,
            email=email,
            password=password,
            use_ssl=True
        )
    
    @staticmethod
    def get_outlook_imap_config(email: str, password: str):
        """
        Get Outlook/Office 365 IMAP configuration
        
        Args:
            email: Outlook email address
            password: Email password
            
        Returns:
            EmailReceiver instance configured for Outlook
        """
        return EmailReceiver(
            imap_server="outlook.office365.com",
            imap_port=993,
            email=email,
            password=password,
            use_ssl=True
        )
