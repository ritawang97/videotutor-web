# -*- coding: utf-8 -*-
"""
Gmail OAuth 2.0 Authentication Module
Handles browser-based OAuth login and token management
"""
import logging
import json
import base64
import http.server
import socketserver
import urllib.parse
import webbrowser
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Tuple
import requests
from app.config import APPDATA_PATH

logger = logging.getLogger(__name__)

# OAuth 2.0 Configuration
# Note: You need to create OAuth credentials in Google Cloud Console
# https://console.cloud.google.com/apis/credentials
OAUTH_CLIENT_ID = "YOUR_CLIENT_ID_HERE"  # Replace with your OAuth Client ID
OAUTH_CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE"  # Replace with your OAuth Client Secret
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = [
    "https://mail.google.com/",  # Full Gmail access including IMAP
    "https://www.googleapis.com/auth/gmail.send",  # Send emails
]

# Token storage file
TOKEN_FILE = APPDATA_PATH / "gmail_oauth_token.json"


class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
    """Handle OAuth callback"""
    
    def do_GET(self):
        """Handle GET request from OAuth callback"""
        if self.path.startswith('/callback'):
            # Parse query parameters
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = query_params.get('code', [None])[0]
            error = query_params.get('error', [None])[0]
            
            if error:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(f"""
                    <html>
                    <body>
                        <h1>Authorization Failed</h1>
                        <p>Error: {error}</p>
                        <p>You can close this window.</p>
                    </body>
                    </html>
                """.encode())
                self.server.auth_code = None
                self.server.auth_error = error
            elif code:
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write("""
                    <html>
                    <body>
                        <h1>Authorization Successful!</h1>
                        <p>You can close this window and return to the application.</p>
                    </body>
                    </html>
                """.encode())
                self.server.auth_code = code
                self.server.auth_error = None
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write("""
                    <html>
                    <body>
                        <h1>Invalid Request</h1>
                        <p>No authorization code received.</p>
                    </body>
                    </html>
                """.encode())
                self.server.auth_code = None
                self.server.auth_error = "No code received"
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress log messages"""
        pass


class GmailOAuth:
    """Gmail OAuth 2.0 authentication handler"""
    
    def __init__(self, client_id: str = None, client_secret: str = None):
        """
        Initialize OAuth handler
        
        Args:
            client_id: OAuth Client ID (if None, uses default)
            client_secret: OAuth Client Secret (if None, uses default)
        """
        self.client_id = client_id or OAUTH_CLIENT_ID
        self.client_secret = client_secret or OAUTH_CLIENT_SECRET
        self.token_file = TOKEN_FILE
    
    def get_authorization_url(self) -> str:
        """Generate OAuth authorization URL"""
        params = {
            'client_id': self.client_id,
            'redirect_uri': REDIRECT_URI,
            'scope': ' '.join(SCOPES),
            'response_type': 'code',
            'access_type': 'offline',  # Required to get refresh token
            'prompt': 'consent',  # Force consent to get refresh token
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
        return auth_url
    
    def start_callback_server(self, port: int = 8080) -> Tuple[http.server.HTTPServer, threading.Thread]:
        """Start local server to receive OAuth callback"""
        server = socketserver.TCPServer(("", port), OAuthCallbackHandler)
        server.auth_code = None
        server.auth_error = None
        
        def run_server():
            server.handle_request()
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        
        return server, thread
    
    def exchange_code_for_tokens(self, code: str) -> Dict:
        """Exchange authorization code for access and refresh tokens"""
        token_url = "https://oauth2.googleapis.com/token"
        
        data = {
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code',
        }
        
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        
        tokens = response.json()
        return tokens
    
    def refresh_access_token(self, refresh_token: str) -> Dict:
        """Refresh access token using refresh token"""
        token_url = "https://oauth2.googleapis.com/token"
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }
        
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        
        tokens = response.json()
        return tokens
    
    def save_tokens(self, tokens: Dict):
        """Save tokens to file"""
        try:
            with open(self.token_file, 'w') as f:
                json.dump(tokens, f, indent=2)
            logger.info(f"Tokens saved to {self.token_file}")
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            raise
    
    def load_tokens(self) -> Optional[Dict]:
        """Load tokens from file"""
        try:
            if self.token_file.exists():
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                logger.info("Tokens loaded from file")
                return tokens
        except Exception as e:
            logger.error(f"Failed to load tokens: {e}")
        return None
    
    def get_valid_access_token(self) -> Optional[str]:
        """Get a valid access token (refresh if needed)"""
        tokens = self.load_tokens()
        if not tokens:
            return None
        
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        
        if not access_token:
            return None
        
        # Check if token is expired (with 5 minute buffer)
        expires_at = tokens.get('expires_at', 0)
        if time.time() >= expires_at - 300:  # Refresh 5 minutes before expiry
            if refresh_token:
                try:
                    logger.info("Access token expired, refreshing...")
                    new_tokens = self.refresh_access_token(refresh_token)
                    access_token = new_tokens.get('access_token')
                    
                    # Update tokens
                    tokens['access_token'] = access_token
                    if 'refresh_token' in new_tokens:
                        tokens['refresh_token'] = new_tokens['refresh_token']
                    tokens['expires_at'] = time.time() + new_tokens.get('expires_in', 3600)
                    
                    self.save_tokens(tokens)
                    logger.info("Access token refreshed successfully")
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}")
                    return None
            else:
                logger.error("No refresh token available")
                return None
        
        return access_token
    
    def authenticate_in_browser(self) -> bool:
        """
        Open browser for OAuth authentication
        
        Returns:
            True if authentication successful, False otherwise
        """
        if self.client_id == "YOUR_CLIENT_ID_HERE" or not self.client_secret:
            raise Exception(
                "OAuth credentials not configured. Please set OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET.\n"
                "Get credentials from: https://console.cloud.google.com/apis/credentials"
            )
        
        # Start callback server
        server, thread = self.start_callback_server()
        
        # Get authorization URL
        auth_url = self.get_authorization_url()
        
        # Open browser
        logger.info(f"Opening browser for OAuth authentication: {auth_url}")
        webbrowser.open(auth_url)
        
        # Wait for callback (with timeout)
        timeout = 120  # 2 minutes
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if server.auth_code:
                code = server.auth_code
                try:
                    # Exchange code for tokens
                    tokens = self.exchange_code_for_tokens(code)
                    
                    # Calculate expiration time
                    tokens['expires_at'] = time.time() + tokens.get('expires_in', 3600)
                    
                    # Save tokens
                    self.save_tokens(tokens)
                    
                    logger.info("OAuth authentication successful")
                    return True
                except Exception as e:
                    logger.error(f"Failed to exchange code for tokens: {e}")
                    return False
            elif server.auth_error:
                logger.error(f"OAuth error: {server.auth_error}")
                return False
            
            time.sleep(0.5)
        
        logger.error("OAuth authentication timeout")
        return False
    
    def generate_xoauth2_string(self, email: str) -> str:
        """
        Generate XOAUTH2 authentication string for IMAP/SMTP
        
        Args:
            email: Email address
            
        Returns:
            XOAUTH2 authentication string
        """
        access_token = self.get_valid_access_token()
        if not access_token:
            raise Exception("No valid access token available. Please authenticate first.")
        
        auth_string = f"user={email}\x01auth=Bearer {access_token}\x01\x01"
        return base64.b64encode(auth_string.encode()).decode()


def authenticate_gmail_oauth(client_id: str = None, client_secret: str = None) -> bool:
    """
    Convenience function to authenticate Gmail via OAuth
    
    Args:
        client_id: OAuth Client ID (optional)
        client_secret: OAuth Client Secret (optional)
        
    Returns:
        True if authentication successful
    """
    oauth = GmailOAuth(client_id, client_secret)
    return oauth.authenticate_in_browser()


def get_gmail_oauth_token(email: str) -> Optional[str]:
    """
    Get XOAUTH2 token string for Gmail
    
    Args:
        email: Email address
        
    Returns:
        XOAUTH2 authentication string or None if not authenticated
    """
    oauth = GmailOAuth()
    try:
        return oauth.generate_xoauth2_string(email)
    except Exception as e:
        logger.error(f"Failed to get OAuth token: {e}")
        return None
