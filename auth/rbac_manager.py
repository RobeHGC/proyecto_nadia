"""Role-Based Access Control (RBAC) manager."""
from typing import Dict, List, Set, Optional
from enum import Enum
from functools import wraps
import asyncio


class UserRole(Enum):
    """User roles with hierarchical permissions."""
    ADMIN = "admin"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class Permission(Enum):
    """System permissions."""
    # Message permissions
    MESSAGE_READ = "message:read"
    MESSAGE_WRITE = "message:write"
    MESSAGE_DELETE = "message:delete"
    MESSAGE_APPROVE = "message:approve"
    MESSAGE_REJECT = "message:reject"
    
    # User permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    USER_MANAGE_ROLES = "user:manage_roles"
    
    # Dashboard permissions
    DASHBOARD_ACCESS = "dashboard:access"
    DASHBOARD_REVIEW = "dashboard:review"
    DASHBOARD_ANALYTICS = "dashboard:analytics"
    DASHBOARD_SETTINGS = "dashboard:settings"
    
    # System permissions
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOGS = "system:logs"
    SYSTEM_HEALTH = "system:health"
    SYSTEM_AUDIT = "system:audit"
    
    # API permissions
    API_KEY_MANAGE = "api:key_manage"
    API_RATE_LIMIT_OVERRIDE = "api:rate_limit_override"


class RBACManager:
    """Manages role-based access control."""
    
    def __init__(self):
        # Define role permissions
        self.role_permissions: Dict[UserRole, Set[Permission]] = {
            UserRole.ADMIN: {
                # Admin has all permissions
                *Permission
            },
            UserRole.REVIEWER: {
                # Reviewer permissions
                Permission.MESSAGE_READ,
                Permission.MESSAGE_APPROVE,
                Permission.MESSAGE_REJECT,
                Permission.USER_READ,
                Permission.DASHBOARD_ACCESS,
                Permission.DASHBOARD_REVIEW,
                Permission.DASHBOARD_ANALYTICS,
                Permission.SYSTEM_HEALTH,
            },
            UserRole.VIEWER: {
                # Viewer permissions (read-only)
                Permission.MESSAGE_READ,
                Permission.USER_READ,
                Permission.DASHBOARD_ACCESS,
                Permission.DASHBOARD_ANALYTICS,
                Permission.SYSTEM_HEALTH,
            }
        }
        
        # Resource-based permission mapping
        self.resource_permissions = {
            # API endpoints to permissions
            'GET /messages': [Permission.MESSAGE_READ],
            'POST /messages': [Permission.MESSAGE_WRITE],
            'DELETE /messages/*': [Permission.MESSAGE_DELETE],
            'POST /messages/*/approve': [Permission.MESSAGE_APPROVE],
            'POST /messages/*/reject': [Permission.MESSAGE_REJECT],
            
            'GET /users': [Permission.USER_READ],
            'GET /users/*': [Permission.USER_READ],
            'PUT /users/*': [Permission.USER_WRITE],
            'DELETE /users/*': [Permission.USER_DELETE],
            'POST /users/*/role': [Permission.USER_MANAGE_ROLES],
            
            'GET /dashboard': [Permission.DASHBOARD_ACCESS],
            'GET /review-queue': [Permission.DASHBOARD_REVIEW],
            'GET /analytics': [Permission.DASHBOARD_ANALYTICS],
            'GET /settings': [Permission.DASHBOARD_SETTINGS],
            'PUT /settings': [Permission.DASHBOARD_SETTINGS],
            
            'GET /system/config': [Permission.SYSTEM_CONFIG],
            'PUT /system/config': [Permission.SYSTEM_CONFIG],
            'GET /system/logs': [Permission.SYSTEM_LOGS],
            'GET /system/health': [Permission.SYSTEM_HEALTH],
            'GET /system/audit': [Permission.SYSTEM_AUDIT],
        }
    
    def get_role(self, role_string: str) -> UserRole:
        """Convert string to UserRole enum."""
        try:
            return UserRole(role_string.lower())
        except ValueError:
            raise ValueError(f"Invalid role: {role_string}")
    
    def has_permission(
        self, 
        user_role: str, 
        permission: Permission
    ) -> bool:
        """Check if a role has a specific permission."""
        role = self.get_role(user_role)
        return permission in self.role_permissions.get(role, set())
    
    def has_any_permission(
        self, 
        user_role: str, 
        permissions: List[Permission]
    ) -> bool:
        """Check if a role has any of the specified permissions."""
        role = self.get_role(user_role)
        user_permissions = self.role_permissions.get(role, set())
        return any(perm in user_permissions for perm in permissions)
    
    def has_all_permissions(
        self, 
        user_role: str, 
        permissions: List[Permission]
    ) -> bool:
        """Check if a role has all of the specified permissions."""
        role = self.get_role(user_role)
        user_permissions = self.role_permissions.get(role, set())
        return all(perm in user_permissions for perm in permissions)
    
    def get_role_permissions(self, user_role: str) -> List[str]:
        """Get all permissions for a role."""
        role = self.get_role(user_role)
        permissions = self.role_permissions.get(role, set())
        return [perm.value for perm in permissions]
    
    def check_endpoint_permission(
        self, 
        user_role: str, 
        method: str, 
        path: str
    ) -> bool:
        """Check if a role can access a specific endpoint."""
        # Normalize endpoint
        endpoint = f"{method.upper()} {path}"
        
        # Check exact match first
        if endpoint in self.resource_permissions:
            required_permissions = self.resource_permissions[endpoint]
            return self.has_any_permission(user_role, required_permissions)
        
        # Check wildcard matches
        for pattern, permissions in self.resource_permissions.items():
            if '*' in pattern:
                # Simple wildcard matching (can be enhanced)
                pattern_parts = pattern.split('*')
                if len(pattern_parts) == 2:
                    prefix, suffix = pattern_parts
                    if endpoint.startswith(prefix) and endpoint.endswith(suffix):
                        return self.has_any_permission(user_role, permissions)
        
        # Default deny if no match
        return False
    
    def get_accessible_endpoints(self, user_role: str) -> List[str]:
        """Get all endpoints accessible by a role."""
        accessible = []
        
        for endpoint, required_permissions in self.resource_permissions.items():
            if self.has_any_permission(user_role, required_permissions):
                accessible.append(endpoint)
        
        return accessible
    
    def require_permission(self, permission: Permission):
        """Decorator to require specific permission for a function."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Extract user role from kwargs or first positional arg
                user_role = kwargs.get('user_role')
                if not user_role and args:
                    # Try to extract from first arg if it's a request object
                    request = args[0]
                    if hasattr(request, 'state') and hasattr(request.state, 'user_role'):
                        user_role = request.state.user_role
                
                if not user_role:
                    raise PermissionError("No user role provided")
                
                if not self.has_permission(user_role, permission):
                    raise PermissionError(f"Permission denied: {permission.value}")
                
                return await func(*args, **kwargs)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Similar logic for sync functions
                user_role = kwargs.get('user_role')
                if not user_role and args:
                    request = args[0]
                    if hasattr(request, 'state') and hasattr(request.state, 'user_role'):
                        user_role = request.state.user_role
                
                if not user_role:
                    raise PermissionError("No user role provided")
                
                if not self.has_permission(user_role, permission):
                    raise PermissionError(f"Permission denied: {permission.value}")
                
                return func(*args, **kwargs)
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def require_any_permission(self, permissions: List[Permission]):
        """Decorator to require any of the specified permissions."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                user_role = kwargs.get('user_role')
                if not user_role and args:
                    request = args[0]
                    if hasattr(request, 'state') and hasattr(request.state, 'user_role'):
                        user_role = request.state.user_role
                
                if not user_role:
                    raise PermissionError("No user role provided")
                
                if not self.has_any_permission(user_role, permissions):
                    perm_names = [p.value for p in permissions]
                    raise PermissionError(f"Permission denied. Requires one of: {perm_names}")
                
                return await func(*args, **kwargs)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                user_role = kwargs.get('user_role')
                if not user_role and args:
                    request = args[0]
                    if hasattr(request, 'state') and hasattr(request.state, 'user_role'):
                        user_role = request.state.user_role
                
                if not user_role:
                    raise PermissionError("No user role provided")
                
                if not self.has_any_permission(user_role, permissions):
                    perm_names = [p.value for p in permissions]
                    raise PermissionError(f"Permission denied. Requires one of: {perm_names}")
                
                return func(*args, **kwargs)
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator


# Global RBAC manager instance
rbac_manager = RBACManager()