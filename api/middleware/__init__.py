"""API middleware for authentication and authorization."""
from api.middleware.auth import (
    AuthenticationMiddleware,
    get_current_user,
    require_user,
    get_optional_user,
    security
)
from api.middleware.rbac import (
    require_permission,
    require_any_permission,
    require_role,
    require_admin,
    require_reviewer,
    check_endpoint_permission,
    RBACMiddleware
)

__all__ = [
    # Auth middleware
    'AuthenticationMiddleware',
    'get_current_user',
    'require_user',
    'get_optional_user',
    'security',
    # RBAC middleware
    'require_permission',
    'require_any_permission',
    'require_role',
    'require_admin',
    'require_reviewer',
    'check_endpoint_permission',
    'RBACMiddleware'
]