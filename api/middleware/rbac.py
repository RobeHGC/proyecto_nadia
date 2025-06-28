"""Role-Based Access Control middleware for API endpoints."""
from typing import List, Optional
from fastapi import HTTPException, Request, Depends
from functools import wraps

from auth.rbac_manager import rbac_manager, Permission, UserRole
from api.middleware.auth import get_current_user
from utils.logging_config import get_logger

logger = get_logger(__name__)


def require_permission(permission: Permission):
    """Decorator to require specific permission for an endpoint."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs
            user = kwargs.get('current_user')
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required"
                )
            
            # Check permission
            if not rbac_manager.has_permission(user['role'], permission):
                logger.warning(
                    f"Permission denied: User {user['email']} (role: {user['role']}) "
                    f"attempted to access resource requiring {permission.value}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required: {permission.value}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_any_permission(permissions: List[Permission]):
    """Decorator to require any of the specified permissions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs
            user = kwargs.get('current_user')
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required"
                )
            
            # Check permissions
            if not rbac_manager.has_any_permission(user['role'], permissions):
                perm_values = [p.value for p in permissions]
                logger.warning(
                    f"Permission denied: User {user['email']} (role: {user['role']}) "
                    f"attempted to access resource requiring one of {perm_values}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required one of: {perm_values}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_role(role: UserRole):
    """Decorator to require specific role for an endpoint."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs
            user = kwargs.get('current_user')
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required"
                )
            
            # Check role
            user_role = rbac_manager.get_role(user['role'])
            if user_role != role:
                logger.warning(
                    f"Role denied: User {user['email']} (role: {user['role']}) "
                    f"attempted to access resource requiring role {role.value}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient role. Required: {role.value}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_admin():
    """Shorthand decorator to require admin role."""
    return require_role(UserRole.ADMIN)


def require_reviewer():
    """Shorthand decorator to require reviewer role or higher."""
    return require_any_permission([
        Permission.MESSAGE_APPROVE,
        Permission.MESSAGE_REJECT
    ])


async def check_endpoint_permission(
    request: Request,
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Check if user has permission to access current endpoint."""
    method = request.method
    path = request.url.path
    
    # Remove path parameters for matching
    # e.g., /users/123 -> /users/*
    path_parts = path.split('/')
    normalized_path = []
    
    for part in path_parts:
        # Check if part looks like an ID (UUID or numeric)
        if part and (
            part.replace('-', '').replace('_', '').isalnum() and 
            len(part) > 8
        ):
            normalized_path.append('*')
        else:
            normalized_path.append(part)
    
    normalized_path_str = '/'.join(normalized_path)
    
    # Check permission
    if not rbac_manager.check_endpoint_permission(
        current_user['role'], 
        method, 
        normalized_path_str
    ):
        logger.warning(
            f"Endpoint permission denied: User {current_user['email']} "
            f"(role: {current_user['role']}) attempted {method} {path}"
        )
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions for this endpoint"
        )
    
    return current_user


class RBACMiddleware:
    """Middleware for automatic RBAC checks on endpoints."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract method and path
            method = scope["method"]
            path = scope["path"]
            
            # Skip RBAC for public paths
            if self._is_public_path(path):
                await self.app(scope, receive, send)
                return
            
            # For other paths, RBAC will be handled by endpoint decorators
            # This middleware just logs the access attempt
            logger.debug(f"RBAC check for {method} {path}")
        
        await self.app(scope, receive, send)
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path should skip RBAC."""
        public_paths = [
            '/health',
            '/docs',
            '/openapi.json',
            '/auth/login',
            '/auth/callback',
            '/auth/refresh'
        ]
        
        return any(path.startswith(p) for p in public_paths)