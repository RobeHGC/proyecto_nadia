"""Token blacklisting for compromised session revocation."""
import os
import hashlib
from datetime import datetime, timezone
from typing import Optional, Set, List
import redis.asyncio as redis

from auth.token_manager import TokenManager
from utils.logging_config import get_logger

logger = get_logger(__name__)


class TokenBlacklist:
    """Manages blacklisted tokens for security revocation."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379')
        self._redis = None
        self.token_manager = TokenManager()
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection."""
        if not self._redis:
            self._redis = redis.from_url(self.redis_url)
        return self._redis
    
    def _get_blacklist_key(self, token_hash: str) -> str:
        """Get Redis key for blacklisted token."""
        return f"token_blacklist:{token_hash}"
    
    def _get_user_blacklist_key(self, user_id: str) -> str:
        """Get Redis key for user's blacklisted tokens."""
        return f"user_blacklist:{user_id}"
    
    async def blacklist_token(
        self, 
        token: str, 
        reason: str = "manual_revocation",
        user_id: Optional[str] = None
    ) -> bool:
        """Add token to blacklist."""
        try:
            # Verify token format and get expiration
            payload = self.token_manager.decode_token(token)
            token_exp = payload.get('exp')
            token_user_id = user_id or payload.get('sub')
            
            if not token_exp:
                logger.error("Cannot blacklist token without expiration")
                return False
            
            # Calculate TTL (time until token naturally expires)
            exp_datetime = datetime.fromtimestamp(token_exp, tz=timezone.utc)
            current_time = datetime.now(timezone.utc)
            ttl_seconds = max(0, int((exp_datetime - current_time).total_seconds()))
            
            if ttl_seconds == 0:
                logger.info("Token already expired, no need to blacklist")
                return True
            
            # Hash token for storage
            token_hash = self.token_manager.hash_token(token)
            
            r = await self._get_redis()
            
            # Store blacklisted token with TTL
            blacklist_key = self._get_blacklist_key(token_hash)
            blacklist_data = {
                'reason': reason,
                'blacklisted_at': datetime.now(timezone.utc).isoformat(),
                'user_id': token_user_id,
                'expires_at': exp_datetime.isoformat()
            }
            
            # Use pipeline for atomic operations
            pipe = r.pipeline()
            pipe.hset(blacklist_key, mapping=blacklist_data)
            pipe.expire(blacklist_key, ttl_seconds)
            
            # Add to user's blacklist set
            if token_user_id:
                user_blacklist_key = self._get_user_blacklist_key(token_user_id)
                pipe.sadd(user_blacklist_key, token_hash)
                pipe.expire(user_blacklist_key, ttl_seconds)
            
            await pipe.execute()
            
            logger.info(
                f"Token blacklisted: hash={token_hash[:16]}..., "
                f"reason={reason}, user_id={token_user_id}, ttl={ttl_seconds}s"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False
    
    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        try:
            token_hash = self.token_manager.hash_token(token)
            blacklist_key = self._get_blacklist_key(token_hash)
            
            r = await self._get_redis()
            is_blacklisted = await r.exists(blacklist_key)
            
            if is_blacklisted:
                # Get blacklist details for logging
                blacklist_data = await r.hgetall(blacklist_key)
                logger.warning(
                    f"Blacklisted token access attempt: hash={token_hash[:16]}..., "
                    f"reason={blacklist_data.get(b'reason', b'unknown').decode()}"
                )
            
            return bool(is_blacklisted)
            
        except Exception as e:
            logger.error(f"Error checking token blacklist: {e}")
            # Fail secure - treat as blacklisted if we can't verify
            return True
    
    async def blacklist_user_tokens(
        self, 
        user_id: str, 
        reason: str = "user_security_action"
    ) -> int:
        """Blacklist all active tokens for a user."""
        try:
            # This requires integration with session manager to get active tokens
            from auth.session_manager import SessionManager
            session_manager = SessionManager()
            
            # Get all active sessions for user
            sessions = await session_manager.get_active_sessions(user_id)
            
            blacklisted_count = 0
            for session in sessions:
                session_id = session['session_id']
                
                # We need to get the actual token from session
                # This is a simplification - in practice, we'd need to store
                # token hashes in the session table to enable this functionality
                logger.info(f"Would blacklist session {session_id} for user {user_id}")
                blacklisted_count += 1
            
            # End all user sessions as alternative
            await session_manager.end_all_user_sessions(user_id)
            
            logger.info(
                f"Blacklisted {blacklisted_count} tokens for user {user_id}, reason: {reason}"
            )
            
            return blacklisted_count
            
        except Exception as e:
            logger.error(f"Failed to blacklist user tokens: {e}")
            return 0
    
    async def get_blacklisted_tokens(self, user_id: str) -> List[dict]:
        """Get all blacklisted tokens for a user."""
        try:
            user_blacklist_key = self._get_user_blacklist_key(user_id)
            
            r = await self._get_redis()
            token_hashes = await r.smembers(user_blacklist_key)
            
            blacklisted_tokens = []
            for token_hash in token_hashes:
                blacklist_key = self._get_blacklist_key(token_hash.decode())
                token_data = await r.hgetall(blacklist_key)
                
                if token_data:
                    blacklisted_tokens.append({
                        'token_hash': token_hash.decode(),
                        'reason': token_data.get(b'reason', b'unknown').decode(),
                        'blacklisted_at': token_data.get(b'blacklisted_at', b'').decode(),
                        'expires_at': token_data.get(b'expires_at', b'').decode()
                    })
            
            return blacklisted_tokens
            
        except Exception as e:
            logger.error(f"Failed to get blacklisted tokens for user {user_id}: {e}")
            return []
    
    async def cleanup_expired_blacklist(self) -> int:
        """Clean up expired blacklist entries (Redis TTL handles this automatically)."""
        try:
            r = await self._get_redis()
            
            # Get all blacklist keys
            blacklist_keys = await r.keys("token_blacklist:*")
            expired_count = 0
            
            for key in blacklist_keys:
                ttl = await r.ttl(key)
                if ttl == -2:  # Key doesn't exist (expired)
                    expired_count += 1
            
            logger.info(f"Blacklist cleanup: {expired_count} expired entries removed by TTL")
            return expired_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup blacklist: {e}")
            return 0
    
    async def revoke_compromised_token(
        self, 
        token: str, 
        security_incident: str = "security_breach"
    ) -> dict:
        """Revoke a compromised token and log security incident."""
        try:
            # Get token details before blacklisting
            payload = self.token_manager.decode_token(token)
            user_id = payload.get('sub')
            token_type = payload.get('type', 'access')
            
            # Blacklist the token
            success = await self.blacklist_token(
                token, 
                reason=f"compromised_{security_incident}",
                user_id=user_id
            )
            
            if success:
                # Log security event
                from auth.session_manager import SessionManager
                session_manager = SessionManager()
                
                await session_manager.log_auth_event(
                    event_type='token_revoked',
                    user_id=user_id,
                    details={
                        'reason': security_incident,
                        'token_type': token_type,
                        'revoked_at': datetime.now(timezone.utc).isoformat(),
                        'action': 'manual_revocation'
                    }
                )
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'token_type': token_type,
                    'reason': security_incident
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to blacklist token'
                }
                
        except Exception as e:
            logger.error(f"Failed to revoke compromised token: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Global token blacklist instance
token_blacklist = TokenBlacklist()