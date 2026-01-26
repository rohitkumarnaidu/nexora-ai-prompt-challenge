"""
Authentication middleware for protecting API endpoints.

This module provides decorators and utilities for validating JWT tokens
and enforcing role-based access control.
"""

import json
from functools import wraps
from typing import Dict, Any, List, Optional, Callable
import structlog

from .config import settings
from .utils import create_api_response, parse_lambda_event
from .models import UserRole
from .rbac import Permission, rbac_manager, check_permission, check_resource_access
from ..services.auth.handler import jwt_service, cognito_service

logger = structlog.get_logger()


class AuthenticationError(Exception):
    """Authentication-related errors."""
    
    def __init__(self, message: str, error_code: str, status_code: int = 401):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


class AuthorizationError(Exception):
    """Authorization-related errors."""
    
    def __init__(self, message: str, error_code: str, status_code: int = 403):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


def extract_token_from_event(event: Dict[str, Any]) -> Optional[str]:
    """Extract JWT token from Lambda event."""
    headers = event.get("headers", {})
    
    # Check Authorization header
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]  # Remove "Bearer " prefix
    
    # Check query parameters
    query_params = event.get("queryStringParameters") or {}
    if "token" in query_params:
        return query_params["token"]
    
    # Check request context (for API Gateway authorizers)
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    if "token" in authorizer:
        return authorizer["token"]
    
    return None


def validate_jwt_token(token: str) -> Dict[str, Any]:
    """Validate JWT token and return payload."""
    if not token:
        raise AuthenticationError(
            "Missing authentication token",
            "MISSING_TOKEN"
        )
    
    validation_result = jwt_service.validate_token(token, "access")
    
    if not validation_result["valid"]:
        error_message = validation_result.get("error", "Invalid token")
        
        if "expired" in error_message.lower():
            raise AuthenticationError(
                "Token has expired",
                "TOKEN_EXPIRED"
            )
        else:
            raise AuthenticationError(
                "Invalid authentication token",
                "INVALID_TOKEN"
            )
    
    return validation_result["payload"]


def validate_cognito_token(token: str) -> Dict[str, Any]:
    """Validate Cognito access token and return user info."""
    if not token:
        raise AuthenticationError(
            "Missing authentication token",
            "MISSING_TOKEN"
        )
    
    validation_result = cognito_service.validate_token(token)
    
    if not validation_result["success"]:
        error_code = validation_result.get("error_code", "INVALID_TOKEN")
        error_message = validation_result.get("error_message", "Invalid token")
        
        if "expired" in error_message.lower() or "NotAuthorizedException" in error_code:
            raise AuthenticationError(
                "Token has expired or is invalid",
                "TOKEN_EXPIRED"
            )
        else:
            raise AuthenticationError(
                "Invalid authentication token",
                "INVALID_TOKEN"
            )
    
    return {
        "cognito_sub": validation_result["cognito_sub"],
        "email": validation_result["email"],
        "tenant_id": validation_result["tenant_id"],
        "user_attributes": validation_result["user_attributes"]
    }


def check_role_permissions(user_role: str, required_roles: List[str]) -> bool:
    """Check if user role has required permissions (legacy method for backward compatibility)."""
    if not required_roles:
        return True  # No specific role required
    
    try:
        user_role_enum = UserRole(user_role)
    except ValueError:
        logger.warning(f"Invalid user role: {user_role}")
        return False
    
    # Define role hierarchy (higher roles include lower role permissions)
    role_hierarchy = {
        "ADMIN": ["ADMIN", "MEMBER", "CREATOR"],
        "MEMBER": ["MEMBER", "CREATOR"],
        "CREATOR": ["CREATOR"]
    }
    
    user_permissions = role_hierarchy.get(user_role, [user_role])
    
    return any(role in user_permissions for role in required_roles)


def check_permission_access(user_role: str, required_permissions: List[Permission]) -> bool:
    """Check if user role has required permissions using the RBAC system."""
    if not required_permissions:
        return True  # No specific permissions required
    
    try:
        user_role_enum = UserRole(user_role)
    except ValueError:
        logger.warning(f"Invalid user role: {user_role}")
        return False
    
    return rbac_manager.has_any_permission(user_role_enum, required_permissions)


def check_tenant_access(user_tenant_id: str, requested_tenant_id: str) -> bool:
    """Check if user has access to the requested tenant."""
    return user_tenant_id == requested_tenant_id


def require_auth(
    token_type: str = "jwt",  # "jwt" or "cognito"
    required_roles: Optional[List[str]] = None,
    required_permissions: Optional[List[Permission]] = None,
    check_tenant: bool = True,
    resource_permission: Optional[Permission] = None
):
    """
    Decorator to require authentication for Lambda functions.
    
    Args:
        token_type: Type of token to validate ("jwt" or "cognito")
        required_roles: List of roles that are allowed to access the endpoint (legacy)
        required_permissions: List of permissions required to access the endpoint
        check_tenant: Whether to enforce tenant-based access control
        resource_permission: Permission required for resource access (with tenant check)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            try:
                # Extract token from event
                token = extract_token_from_event(event)
                
                # Validate token based on type
                if token_type == "jwt":
                    user_info = validate_jwt_token(token)
                    user_id = user_info["sub"]
                    tenant_id = user_info["tenant_id"]
                    role = user_info["role"]
                elif token_type == "cognito":
                    user_info = validate_cognito_token(token)
                    user_id = user_info["cognito_sub"]
                    tenant_id = user_info["tenant_id"]
                    role = user_info["user_attributes"].get("custom:user_role", "CREATOR")
                else:
                    raise AuthenticationError(
                        "Invalid token type configuration",
                        "INVALID_TOKEN_TYPE"
                    )
                
                # Check role permissions (legacy support)
                if required_roles and not check_role_permissions(role, required_roles):
                    raise AuthorizationError(
                        f"Insufficient permissions. Required roles: {required_roles}",
                        "INSUFFICIENT_PERMISSIONS"
                    )
                
                # Check RBAC permissions
                if required_permissions and not check_permission_access(role, required_permissions):
                    raise AuthorizationError(
                        f"Insufficient permissions. Required permissions: {[p.value for p in required_permissions]}",
                        "INSUFFICIENT_PERMISSIONS"
                    )
                
                # Check tenant access if enabled
                if check_tenant:
                    parsed_event = parse_lambda_event(event)
                    path_params = parsed_event.get("path_parameters", {})
                    query_params = parsed_event.get("query_parameters", {})
                    body = parsed_event.get("body", {})
                    
                    # Look for tenant_id in various places
                    requested_tenant_id = (
                        path_params.get("tenant_id") or
                        query_params.get("tenant_id") or
                        body.get("tenant_id")
                    )
                    
                    if requested_tenant_id and not check_tenant_access(tenant_id, requested_tenant_id):
                        raise AuthorizationError(
                            "Access denied to requested tenant",
                            "TENANT_ACCESS_DENIED"
                        )
                
                # Check resource-based permissions
                if resource_permission:
                    parsed_event = parse_lambda_event(event)
                    path_params = parsed_event.get("path_parameters", {})
                    query_params = parsed_event.get("query_parameters", {})
                    body = parsed_event.get("body", {})
                    
                    resource_tenant_id = (
                        path_params.get("tenant_id") or
                        query_params.get("tenant_id") or
                        body.get("tenant_id") or
                        tenant_id  # Default to user's tenant
                    )
                    
                    try:
                        user_role_enum = UserRole(role)
                        if not check_resource_access(user_role_enum, tenant_id, resource_tenant_id, resource_permission):
                            raise AuthorizationError(
                                f"Insufficient permissions for resource access. Required: {resource_permission.value}",
                                "RESOURCE_ACCESS_DENIED"
                            )
                    except ValueError:
                        raise AuthorizationError(
                            f"Invalid user role: {role}",
                            "INVALID_USER_ROLE"
                        )
                
                # Add user info to event for use in the handler
                event["user_info"] = {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "role": role,
                    "token_type": token_type,
                    "raw_user_info": user_info
                }
                
                # Call the original function
                return func(event, context)
                
            except (AuthenticationError, AuthorizationError) as e:
                logger.warning(
                    "Authentication/Authorization error",
                    error_code=e.error_code,
                    message=e.message,
                    path=event.get("path", "unknown")
                )
                
                return create_api_response(
                    success=False,
                    message=e.message,
                    error_code=e.error_code,
                    status_code=e.status_code
                )
                
            except Exception as e:
                logger.error(
                    "Unexpected authentication error",
                    error=str(e),
                    path=event.get("path", "unknown")
                )
                
                return create_api_response(
                    success=False,
                    message="Authentication failed",
                    error_code="AUTH_ERROR",
                    status_code=500
                )
        
        return wrapper
    return decorator


def require_jwt_auth(required_roles: Optional[List[str]] = None, check_tenant: bool = True):
    """Decorator to require JWT authentication."""
    return require_auth(token_type="jwt", required_roles=required_roles, check_tenant=check_tenant)


def require_cognito_auth(required_roles: Optional[List[str]] = None, check_tenant: bool = True):
    """Decorator to require Cognito authentication."""
    return require_auth(token_type="cognito", required_roles=required_roles, check_tenant=check_tenant)


def require_admin_role(token_type: str = "jwt", check_tenant: bool = True):
    """Decorator to require admin role."""
    return require_auth(token_type=token_type, required_roles=["ADMIN"], check_tenant=check_tenant)


def require_member_role(token_type: str = "jwt", check_tenant: bool = True):
    """Decorator to require member role or higher."""
    return require_auth(token_type=token_type, required_roles=["ADMIN", "MEMBER"], check_tenant=check_tenant)


# New RBAC-based decorators

def require_permission(permission: Permission, token_type: str = "jwt", check_tenant: bool = True):
    """Decorator to require a specific permission."""
    return require_auth(
        token_type=token_type,
        required_permissions=[permission],
        check_tenant=check_tenant
    )


def require_any_permission(permissions: List[Permission], token_type: str = "jwt", check_tenant: bool = True):
    """Decorator to require any of the specified permissions."""
    return require_auth(
        token_type=token_type,
        required_permissions=permissions,
        check_tenant=check_tenant
    )


def require_resource_access(permission: Permission, token_type: str = "jwt"):
    """Decorator to require resource-based access with tenant isolation."""
    return require_auth(
        token_type=token_type,
        resource_permission=permission,
        check_tenant=True
    )


def require_content_access(action: str = "read", token_type: str = "jwt"):
    """Decorator to require content-related permissions."""
    permission_map = {
        "create": Permission.CONTENT_CREATE,
        "read": Permission.CONTENT_READ,
        "update": Permission.CONTENT_UPDATE,
        "delete": Permission.CONTENT_DELETE,
        "publish": Permission.CONTENT_PUBLISH,
        "schedule": Permission.CONTENT_SCHEDULE,
    }
    
    permission = permission_map.get(action, Permission.CONTENT_READ)
    return require_resource_access(permission, token_type)


def require_user_management(action: str = "read", token_type: str = "jwt"):
    """Decorator to require user management permissions."""
    permission_map = {
        "create": Permission.USER_CREATE,
        "read": Permission.USER_READ,
        "update": Permission.USER_UPDATE,
        "delete": Permission.USER_DELETE,
        "invite": Permission.USER_INVITE,
        "assign_role": Permission.USER_ROLE_ASSIGN,
    }
    
    permission = permission_map.get(action, Permission.USER_READ)
    return require_resource_access(permission, token_type)


def require_tenant_management(action: str = "read", token_type: str = "jwt"):
    """Decorator to require tenant management permissions."""
    permission_map = {
        "read": Permission.TENANT_READ,
        "update": Permission.TENANT_UPDATE,
        "delete": Permission.TENANT_DELETE,
        "settings": Permission.TENANT_SETTINGS_UPDATE,
        "billing": Permission.TENANT_BILLING_READ,
    }
    
    permission = permission_map.get(action, Permission.TENANT_READ)
    return require_resource_access(permission, token_type)


def require_analytics_access(level: str = "read", token_type: str = "jwt"):
    """Decorator to require analytics permissions."""
    permission_map = {
        "read": Permission.ANALYTICS_READ,
        "export": Permission.ANALYTICS_EXPORT,
        "admin": Permission.ANALYTICS_ADMIN,
    }
    
    permission = permission_map.get(level, Permission.ANALYTICS_READ)
    return require_resource_access(permission, token_type)


def get_user_info_from_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract user info from authenticated event."""
    return event.get("user_info")


def get_user_id_from_event(event: Dict[str, Any]) -> Optional[str]:
    """Extract user ID from authenticated event."""
    user_info = get_user_info_from_event(event)
    return user_info["user_id"] if user_info else None


def get_tenant_id_from_event(event: Dict[str, Any]) -> Optional[str]:
    """Extract tenant ID from authenticated event."""
    user_info = get_user_info_from_event(event)
    return user_info["tenant_id"] if user_info else None


def get_user_role_from_event(event: Dict[str, Any]) -> Optional[str]:
    """Extract user role from authenticated event."""
    user_info = get_user_info_from_event(event)
    return user_info["role"] if user_info else None


# Example usage decorators for common patterns
def public_endpoint(func: Callable) -> Callable:
    """Decorator for public endpoints that don't require authentication."""
    return func


def authenticated_endpoint(func: Callable) -> Callable:
    """Decorator for endpoints that require any valid authentication."""
    return require_jwt_auth()(func)


def admin_only_endpoint(func: Callable) -> Callable:
    """Decorator for admin-only endpoints."""
    return require_admin_role()(func)


def tenant_scoped_endpoint(func: Callable) -> Callable:
    """Decorator for endpoints that require tenant-scoped access."""
    return require_jwt_auth(check_tenant=True)(func)