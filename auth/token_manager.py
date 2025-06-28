"""JWT token management for authentication."""
import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
from uuid import UUID

from jose import jwt, JWTError
from dotenv import load_dotenv

load_dotenv()


class TokenManager:
    """Manages JWT tokens for authentication."""
    
    def __init__(self):
        self.secret_key = os.getenv('JWT_SECRET_KEY')
        if not self.secret_key:
            # Generate a secure key if not provided (for development)
            import secrets
            self.secret_key = secrets.token_urlsafe(32)
            print("WARNING: Using generated JWT secret key. Set JWT_SECRET_KEY in production!")
        
        self.algorithm = 'HS256'
        self.access_token_expire_minutes = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
        self.refresh_token_expire_days = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRE_DAYS', '30'))
    
    def create_access_token(
        self, 
        user_id: str,
        email: str,
        role: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create JWT access token."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        
        claims = {
            'sub': user_id,  # Subject (user ID)
            'email': email,
            'role': role,
            'exp': expire,
            'iat': now,
            'type': 'access'
        }
        
        if additional_claims:
            claims.update(additional_claims)
        
        return jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user_id: str) -> str:
        """Create JWT refresh token."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self.refresh_token_expire_days)
        
        claims = {
            'sub': user_id,
            'exp': expire,
            'iat': now,
            'type': 'refresh'
        }
        
        return jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate JWT token."""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm]
            )
            return payload
        except JWTError as e:
            raise ValueError(f"Invalid token: {str(e)}")
    
    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """Verify access token and return claims."""
        payload = self.decode_token(token)
        
        if payload.get('type') != 'access':
            raise ValueError("Invalid token type")
        
        return payload
    
    def verify_refresh_token(self, token: str) -> str:
        """Verify refresh token and return user ID."""
        payload = self.decode_token(token)
        
        if payload.get('type') != 'refresh':
            raise ValueError("Invalid token type")
        
        return payload['sub']
    
    def hash_token(self, token: str) -> str:
        """Create SHA256 hash of token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def create_token_pair(
        self,
        user_id: str,
        email: str,
        role: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """Create both access and refresh tokens."""
        access_token = self.create_access_token(
            user_id=user_id,
            email=email,
            role=role,
            additional_claims=additional_claims
        )
        refresh_token = self.create_refresh_token(user_id)
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': self.access_token_expire_minutes * 60
        }
    
    def extract_token_from_header(self, authorization: str) -> str:
        """Extract token from Authorization header."""
        if not authorization:
            raise ValueError("No authorization header")
        
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise ValueError("Invalid authorization header format")
        
        return parts[1]
    
    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired."""
        try:
            payload = self.decode_token(token)
            exp = payload.get('exp')
            if not exp:
                return True
            
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            return exp_datetime < datetime.now(timezone.utc)
        except:
            return True
    
    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """Get token expiration datetime."""
        try:
            payload = self.decode_token(token)
            exp = payload.get('exp')
            if exp:
                return datetime.fromtimestamp(exp, tz=timezone.utc)
            return None
        except:
            return None