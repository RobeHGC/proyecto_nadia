"""API middleware for authentication and authorization."""
try:
    from api.middleware.auth import (
        AuthenticationMiddleware,
        get_current_user,
        require_user,
        get_optional_user,
        security
    )
except ImportError:
    # Graceful degradation if auth dependencies missing
    AuthenticationMiddleware = None
    get_current_user = None
    require_user = None
    get_optional_user = None
    security = None

try:
    from api.middleware.rbac import (
        require_permission,
        require_any_permission,
        require_role,
        require_admin,
        require_reviewer,
        check_endpoint_permission,
        RBACMiddleware
    )
except ImportError:
    # Graceful degradation if RBAC dependencies missing
    require_permission = None
    require_any_permission = None
    require_role = None
    require_admin = None
    require_reviewer = None
    check_endpoint_permission = None
    RBACMiddleware = None

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