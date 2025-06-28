"""OAuth provider integration for Google and GitHub authentication."""
import os
import httpx
import secrets
from typing import Dict, Optional, Any
from urllib.parse import urlencode
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()


class OAuthProvider:
    """Base OAuth provider class."""
    
    def __init__(self):
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.authorize_url = None
        self.token_url = None
        self.userinfo_url = None
        self.scope = None
        
    def get_authorization_url(self, state: str) -> str:
        """Generate OAuth authorization URL."""
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': self.scope,
            'state': state,
            'access_type': 'offline',  # For refresh token
            'prompt': 'select_account'  # Force account selection
        }
        return f"{self.authorize_url}?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'code': code,
            'grant_type': 'authorization_code'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url, data=data)
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from OAuth provider."""
        headers = {'Authorization': f'Bearer {access_token}'}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.userinfo_url, headers=headers)
            response.raise_for_status()
            return response.json()
    
    def normalize_user_info(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize user info to common format."""
        raise NotImplementedError("Subclasses must implement normalize_user_info")


class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth provider implementation."""
    
    def __init__(self):
        super().__init__()
        self.client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
        self.redirect_uri = os.getenv('OAUTH_REDIRECT_URI', 'http://localhost:3000/auth/callback')
        self.authorize_url = 'https://accounts.google.com/o/oauth2/v2/auth'
        self.token_url = 'https://oauth2.googleapis.com/token'
        self.userinfo_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        self.scope = 'openid email profile'
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Google OAuth credentials not configured in environment")
    
    def normalize_user_info(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Google user info."""
        return {
            'oauth_id': user_info['id'],
            'email': user_info['email'],
            'name': user_info.get('name', user_info['email'].split('@')[0]),
            'avatar_url': user_info.get('picture'),
            'oauth_provider': 'google',
            'raw_info': user_info
        }


class GitHubOAuthProvider(OAuthProvider):
    """GitHub OAuth provider implementation."""
    
    def __init__(self):
        super().__init__()
        self.client_id = os.getenv('GITHUB_OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('GITHUB_OAUTH_CLIENT_SECRET')
        self.redirect_uri = os.getenv('OAUTH_REDIRECT_URI', 'http://localhost:3000/auth/callback')
        self.authorize_url = 'https://github.com/login/oauth/authorize'
        self.token_url = 'https://github.com/login/oauth/access_token'
        self.userinfo_url = 'https://api.github.com/user'
        self.scope = 'user:email'
        
        if not self.client_id or not self.client_secret:
            raise ValueError("GitHub OAuth credentials not configured in environment")
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token (GitHub specific)."""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'code': code
        }
        
        headers = {'Accept': 'application/json'}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url, data=data, headers=headers)
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from GitHub (includes fetching email)."""
        headers = {'Authorization': f'token {access_token}'}
        
        async with httpx.AsyncClient() as client:
            # Get basic user info
            response = await client.get(self.userinfo_url, headers=headers)
            response.raise_for_status()
            user_info = response.json()
            
            # If email is not public, fetch from emails endpoint
            if not user_info.get('email'):
                email_response = await client.get(
                    'https://api.github.com/user/emails',
                    headers=headers
                )
                email_response.raise_for_status()
                emails = email_response.json()
                
                # Find primary verified email
                for email in emails:
                    if email.get('primary') and email.get('verified'):
                        user_info['email'] = email['email']
                        break
            
            return user_info
    
    def normalize_user_info(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize GitHub user info."""
        return {
            'oauth_id': str(user_info['id']),
            'email': user_info['email'],
            'name': user_info.get('name') or user_info.get('login'),
            'avatar_url': user_info.get('avatar_url'),
            'oauth_provider': 'github',
            'raw_info': user_info
        }


class OAuthManager:
    """Manager for handling multiple OAuth providers."""
    
    def __init__(self):
        self.providers = {
            'google': GoogleOAuthProvider,
            'github': GitHubOAuthProvider
        }
        self._provider_instances = {}
    
    def get_provider(self, provider_name: str) -> OAuthProvider:
        """Get OAuth provider instance."""
        if provider_name not in self.providers:
            raise ValueError(f"Unsupported OAuth provider: {provider_name}")
        
        if provider_name not in self._provider_instances:
            self._provider_instances[provider_name] = self.providers[provider_name]()
        
        return self._provider_instances[provider_name]
    
    def generate_state_token(self) -> str:
        """Generate secure state token for CSRF protection."""
        return secrets.token_urlsafe(32)
    
    async def handle_callback(
        self, 
        provider_name: str, 
        code: str
    ) -> Dict[str, Any]:
        """Handle OAuth callback and return normalized user info."""
        provider = self.get_provider(provider_name)
        
        # Exchange code for token
        token_response = await provider.exchange_code_for_token(code)
        access_token = token_response.get('access_token')
        
        if not access_token:
            raise ValueError("Failed to obtain access token")
        
        # Get user info
        user_info = await provider.get_user_info(access_token)
        
        # Normalize user info
        normalized_info = provider.normalize_user_info(user_info)
        
        # Add token info
        normalized_info['access_token'] = access_token
        normalized_info['refresh_token'] = token_response.get('refresh_token')
        normalized_info['token_expires_in'] = token_response.get('expires_in')
        
        return normalized_info