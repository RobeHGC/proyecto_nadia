"""Session management for user authentication."""
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any, List
from uuid import UUID
import asyncpg
from ipaddress import ip_address

from auth.token_manager import TokenManager
from database.models import DatabaseManager
from dotenv import load_dotenv

load_dotenv()


class SessionManager:
    """Manages user sessions and authentication state."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.db_url = database_url or os.getenv('DATABASE_URL')
        self.token_manager = TokenManager()
        self.session_timeout_minutes = int(os.getenv('SESSION_TIMEOUT_MINUTES', '30'))
        self.max_sessions_per_user = int(os.getenv('MAX_SESSIONS_PER_USER', '5'))
        self._db = None
    
    async def initialize(self):
        """Initialize database connection."""
        if not self._db:
            self._db = DatabaseManager(self.db_url)
            await self._db.initialize()
    
    async def create_session(
        self,
        user_id: str,
        user_email: str,
        user_role: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new user session."""
        await self.initialize()
        
        # Generate tokens
        tokens = self.token_manager.create_token_pair(
            user_id=user_id,
            email=user_email,
            role=user_role
        )
        
        # Hash tokens for storage
        access_token_hash = self.token_manager.hash_token(tokens['access_token'])
        refresh_token_hash = self.token_manager.hash_token(tokens['refresh_token'])
        
        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self.token_manager.access_token_expire_minutes
        )
        
        # Clean up old sessions if limit exceeded
        await self._cleanup_user_sessions(user_id)
        
        # Create session record
        async with self._db._pool.acquire() as conn:
            session = await conn.fetchrow("""
                INSERT INTO user_sessions (
                    user_id, token_hash, refresh_token_hash,
                    ip_address, user_agent, expires_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, created_at
            """, UUID(user_id), access_token_hash, refresh_token_hash,
                ip_address, user_agent, expires_at)
            
            # Update last login
            await conn.execute("""
                UPDATE users 
                SET last_login = NOW() 
                WHERE id = $1
            """, UUID(user_id))
        
        return {
            'session_id': str(session['id']),
            'tokens': tokens,
            'expires_at': expires_at.isoformat(),
            'created_at': session['created_at'].isoformat()
        }
    
    async def validate_session(
        self, 
        token: str,
        update_activity: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Validate session token and return user info."""
        await self.initialize()
        
        try:
            # Decode and validate token
            payload = self.token_manager.verify_access_token(token)
            user_id = payload['sub']
            
            # Hash token to look up session
            token_hash = self.token_manager.hash_token(token)
            
            async with self._db._pool.acquire() as conn:
                # Get session and user info
                result = await conn.fetchrow("""
                    SELECT 
                        s.id as session_id,
                        s.expires_at,
                        s.is_active,
                        u.id as user_id,
                        u.email,
                        u.name,
                        u.role,
                        u.avatar_url,
                        u.is_active as user_active
                    FROM user_sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.token_hash = $1
                        AND s.is_active = true
                        AND s.expires_at > NOW()
                        AND u.is_active = true
                """, token_hash)
                
                if not result:
                    return None
                
                # Update last activity if requested
                if update_activity:
                    await conn.execute("""
                        UPDATE user_sessions 
                        SET last_activity = NOW() 
                        WHERE id = $1
                    """, result['session_id'])
                
                return {
                    'user_id': str(result['user_id']),
                    'email': result['email'],
                    'name': result['name'],
                    'role': result['role'],
                    'avatar_url': result['avatar_url'],
                    'session_id': str(result['session_id']),
                    'expires_at': result['expires_at'].isoformat()
                }
        
        except ValueError:
            # Invalid token
            return None
    
    async def refresh_session(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refresh session with refresh token."""
        await self.initialize()
        
        try:
            # Verify refresh token
            user_id = self.token_manager.verify_refresh_token(refresh_token)
            refresh_token_hash = self.token_manager.hash_token(refresh_token)
            
            async with self._db._pool.acquire() as conn:
                # Get user and session info
                result = await conn.fetchrow("""
                    SELECT 
                        s.id as session_id,
                        s.ip_address,
                        s.user_agent,
                        u.email,
                        u.role,
                        u.is_active
                    FROM user_sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.refresh_token_hash = $1
                        AND s.is_active = true
                        AND u.is_active = true
                """, refresh_token_hash)
                
                if not result:
                    return None
                
                # Deactivate old session
                await conn.execute("""
                    UPDATE user_sessions 
                    SET is_active = false 
                    WHERE id = $1
                """, result['session_id'])
                
                # Create new session
                return await self.create_session(
                    user_id=user_id,
                    user_email=result['email'],
                    user_role=result['role'],
                    ip_address=result['ip_address'],
                    user_agent=result['user_agent']
                )
        
        except ValueError:
            return None
    
    async def end_session(self, token: str) -> bool:
        """End a user session (logout)."""
        await self.initialize()
        
        token_hash = self.token_manager.hash_token(token)
        
        async with self._db._pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE user_sessions 
                SET is_active = false 
                WHERE token_hash = $1 AND is_active = true
            """, token_hash)
            
            return result.split()[-1] != '0'
    
    async def end_all_user_sessions(self, user_id: str) -> int:
        """End all sessions for a user."""
        await self.initialize()
        
        async with self._db._pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE user_sessions 
                SET is_active = false 
                WHERE user_id = $1 AND is_active = true
            """, UUID(user_id))
            
            return int(result.split()[-1])
    
    async def get_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user."""
        await self.initialize()
        
        async with self._db._pool.acquire() as conn:
            sessions = await conn.fetch("""
                SELECT 
                    id,
                    ip_address,
                    user_agent,
                    created_at,
                    last_activity,
                    expires_at
                FROM user_sessions
                WHERE user_id = $1 
                    AND is_active = true
                    AND expires_at > NOW()
                ORDER BY last_activity DESC
            """, UUID(user_id))
            
            return [
                {
                    'session_id': str(s['id']),
                    'ip_address': s['ip_address'],
                    'user_agent': s['user_agent'],
                    'created_at': s['created_at'].isoformat(),
                    'last_activity': s['last_activity'].isoformat(),
                    'expires_at': s['expires_at'].isoformat()
                }
                for s in sessions
            ]
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        await self.initialize()
        
        async with self._db._pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE user_sessions 
                SET is_active = false 
                WHERE expires_at < NOW() AND is_active = true
            """)
            
            return int(result.split()[-1])
    
    async def _cleanup_user_sessions(self, user_id: str):
        """Clean up old sessions if user exceeds limit."""
        async with self._db._pool.acquire() as conn:
            # Count active sessions
            count = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM user_sessions 
                WHERE user_id = $1 AND is_active = true
            """, UUID(user_id))
            
            # If at limit, deactivate oldest sessions
            if count >= self.max_sessions_per_user:
                await conn.execute("""
                    UPDATE user_sessions 
                    SET is_active = false
                    WHERE id IN (
                        SELECT id 
                        FROM user_sessions
                        WHERE user_id = $1 AND is_active = true
                        ORDER BY last_activity ASC
                        LIMIT $2
                    )
                """, UUID(user_id), count - self.max_sessions_per_user + 1)
    
    async def log_auth_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log authentication event for audit trail."""
        await self.initialize()
        
        async with self._db._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO auth_audit_log (
                    user_id, event_type, ip_address, 
                    user_agent, details
                )
                VALUES ($1, $2, $3, $4, $5)
            """, UUID(user_id) if user_id else None, event_type,
                ip_address, user_agent, details)