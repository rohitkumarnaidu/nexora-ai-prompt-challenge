"""
Role-Based Access Control (RBAC) system for Nexora AI Platform.

This module defines roles, permissions, and access control logic for the platform.
"""

from enum import Enum
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
import structlog

from .models import UserRole

logger = structlog.get_logger()


class Permission(str, Enum):
    """System permissions."""
    
    # Content permissions
    CONTENT_CREATE = "content:create"
    CONTENT_READ = "content:read"
    CONTENT_UPDATE = "content:update"
    CONTENT_DELETE = "content:delete"
    CONTENT_PUBLISH = "content:publish"
    CONTENT_SCHEDULE = "content:schedule"
    
    # User management permissions
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_INVITE = "user:invite"
    USER_ROLE_ASSIGN = "user:role_assign"
    
    # Tenant management permissions
    TENANT_READ = "tenant:read"
    TENANT_UPDATE = "tenant:update"
    TENANT_DELETE = "tenant:delete"
    TENANT_SETTINGS_UPDATE = "tenant:settings_update"
    TENANT_BILLING_READ = "tenant:billing_read"
    TENANT_BILLING_UPDATE = "tenant:billing_update"
    
    # Analytics permissions
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"
    ANALYTICS_ADMIN = "analytics:admin"
    
    # RAG pipeline permissions
    RAG_DOCUMENT_UPLOAD = "rag:document_upload"
    RAG_DOCUMENT_DELETE = "rag:document_delete"
    RAG_PIPELINE_CONFIGURE = "rag:pipeline_configure"
    
    # Publishing permissions
    PUBLISHING_ENDPOINT_CREATE = "publishing:endpoint_create"
    PUBLISHING_ENDPOINT_UPDATE = "publishing:endpoint_update"
    PUBLISHING_ENDPOINT_DELETE = "publishing:endpoint_delete"
    PUBLISHING_EXECUTE = "publishing:execute"
    
    # Workflow permissions
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_UPDATE = "workflow:update"
    WORKFLOW_DELETE = "workflow:delete"
    WORKFLOW_APPROVE = "workflow:approve"
    WORKFLOW_REJECT = "workflow:reject"
    
    # System administration permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_MONITORING = "system:monitoring"
    SYSTEM_LOGS = "system:logs"


@dataclass
class RoleDefinition:
    """Definition of a role with its permissions."""
    name: UserRole
    description: str
    permissions: Set[Permission]
    inherits_from: Optional[UserRole] = None


class RBACManager:
    """Role-Based Access Control manager."""
    
    def __init__(self):
        self._role_definitions = self._initialize_roles()
        self._permission_cache: Dict[str, Set[Permission]] = {}
    
    def _initialize_roles(self) -> Dict[UserRole, RoleDefinition]:
        """Initialize role definitions with their permissions."""
        
        # Creator role - basic content creation permissions
        creator_permissions = {
            Permission.CONTENT_CREATE,
            Permission.CONTENT_READ,
            Permission.CONTENT_UPDATE,
            Permission.CONTENT_DELETE,
            Permission.CONTENT_PUBLISH,
            Permission.CONTENT_SCHEDULE,
            Permission.RAG_DOCUMENT_UPLOAD,
            Permission.RAG_DOCUMENT_DELETE,
            Permission.PUBLISHING_ENDPOINT_CREATE,
            Permission.PUBLISHING_ENDPOINT_UPDATE,
            Permission.PUBLISHING_ENDPOINT_DELETE,
            Permission.PUBLISHING_EXECUTE,
            Permission.WORKFLOW_CREATE,
            Permission.WORKFLOW_READ,
            Permission.WORKFLOW_UPDATE,
            Permission.WORKFLOW_DELETE,
            Permission.ANALYTICS_READ,
        }
        
        # Member role - includes creator permissions plus team collaboration
        member_permissions = creator_permissions | {
            Permission.USER_READ,
            Permission.WORKFLOW_APPROVE,
            Permission.WORKFLOW_REJECT,
            Permission.ANALYTICS_EXPORT,
            Permission.RAG_PIPELINE_CONFIGURE,
        }
        
        # Admin role - includes member permissions plus administrative functions
        admin_permissions = member_permissions | {
            Permission.USER_CREATE,
            Permission.USER_UPDATE,
            Permission.USER_DELETE,
            Permission.USER_INVITE,
            Permission.USER_ROLE_ASSIGN,
            Permission.TENANT_READ,
            Permission.TENANT_UPDATE,
            Permission.TENANT_SETTINGS_UPDATE,
            Permission.TENANT_BILLING_READ,
            Permission.TENANT_BILLING_UPDATE,
            Permission.ANALYTICS_ADMIN,
            Permission.SYSTEM_MONITORING,
            Permission.SYSTEM_LOGS,
        }
        
        return {
            UserRole.CREATOR: RoleDefinition(
                name=UserRole.CREATOR,
                description="Content creator with basic permissions",
                permissions=creator_permissions
            ),
            UserRole.MEMBER: RoleDefinition(
                name=UserRole.MEMBER,
                description="Team member with collaboration permissions",
                permissions=member_permissions,
                inherits_from=UserRole.CREATOR
            ),
            UserRole.ADMIN: RoleDefinition(
                name=UserRole.ADMIN,
                description="Administrator with full tenant permissions",
                permissions=admin_permissions,
                inherits_from=UserRole.MEMBER
            ),
        }
    
    def get_role_permissions(self, role: UserRole) -> Set[Permission]:
        """Get all permissions for a role, including inherited permissions."""
        cache_key = role.value
        
        if cache_key in self._permission_cache:
            return self._permission_cache[cache_key]
        
        if role not in self._role_definitions:
            logger.warning(f"Unknown role: {role}")
            return set()
        
        role_def = self._role_definitions[role]
        permissions = role_def.permissions.copy()
        
        # Add inherited permissions
        if role_def.inherits_from:
            inherited_permissions = self.get_role_permissions(role_def.inherits_from)
            permissions.update(inherited_permissions)
        
        self._permission_cache[cache_key] = permissions
        return permissions
    
    def has_permission(self, user_role: UserRole, permission: Permission) -> bool:
        """Check if a role has a specific permission."""
        role_permissions = self.get_role_permissions(user_role)
        return permission in role_permissions
    
    def has_any_permission(self, user_role: UserRole, permissions: List[Permission]) -> bool:
        """Check if a role has any of the specified permissions."""
        role_permissions = self.get_role_permissions(user_role)
        return any(perm in role_permissions for perm in permissions)
    
    def has_all_permissions(self, user_role: UserRole, permissions: List[Permission]) -> bool:
        """Check if a role has all of the specified permissions."""
        role_permissions = self.get_role_permissions(user_role)
        return all(perm in role_permissions for perm in permissions)
    
    def can_assign_role(self, assigner_role: UserRole, target_role: UserRole) -> bool:
        """Check if a user with assigner_role can assign target_role to another user."""
        # Only admins can assign roles
        if not self.has_permission(assigner_role, Permission.USER_ROLE_ASSIGN):
            return False
        
        # Admins can assign any role equal to or lower than their own
        role_hierarchy = {
            UserRole.CREATOR: 1,
            UserRole.MEMBER: 2,
            UserRole.ADMIN: 3,
        }
        
        assigner_level = role_hierarchy.get(assigner_role, 0)
        target_level = role_hierarchy.get(target_role, 0)
        
        return assigner_level >= target_level
    
    def get_assignable_roles(self, assigner_role: UserRole) -> List[UserRole]:
        """Get list of roles that can be assigned by the given role."""
        if not self.has_permission(assigner_role, Permission.USER_ROLE_ASSIGN):
            return []
        
        role_hierarchy = {
            UserRole.CREATOR: 1,
            UserRole.MEMBER: 2,
            UserRole.ADMIN: 3,
        }
        
        assigner_level = role_hierarchy.get(assigner_role, 0)
        
        return [
            role for role, level in role_hierarchy.items()
            if level <= assigner_level
        ]
    
    def get_role_definition(self, role: UserRole) -> Optional[RoleDefinition]:
        """Get the definition for a specific role."""
        return self._role_definitions.get(role)
    
    def list_all_roles(self) -> List[RoleDefinition]:
        """Get all role definitions."""
        return list(self._role_definitions.values())
    
    def validate_permission_string(self, permission_str: str) -> bool:
        """Validate if a permission string is valid."""
        try:
            Permission(permission_str)
            return True
        except ValueError:
            return False


# Global RBAC manager instance
rbac_manager = RBACManager()


def check_permission(user_role: UserRole, permission: Permission) -> bool:
    """Convenience function to check if a role has a permission."""
    return rbac_manager.has_permission(user_role, permission)


def check_any_permission(user_role: UserRole, permissions: List[Permission]) -> bool:
    """Convenience function to check if a role has any of the permissions."""
    return rbac_manager.has_any_permission(user_role, permissions)


def check_all_permissions(user_role: UserRole, permissions: List[Permission]) -> bool:
    """Convenience function to check if a role has all of the permissions."""
    return rbac_manager.has_all_permissions(user_role, permissions)


def require_permission(permission: Permission):
    """Decorator to require a specific permission for a function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would be used with the auth middleware
            # The actual implementation would extract user role from context
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(permissions: List[Permission]):
    """Decorator to require any of the specified permissions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would be used with the auth middleware
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_all_permissions(permissions: List[Permission]):
    """Decorator to require all of the specified permissions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would be used with the auth middleware
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Resource-based access control helpers

def check_resource_access(
    user_role: UserRole,
    user_tenant_id: str,
    resource_tenant_id: str,
    permission: Permission
) -> bool:
    """
    Check if a user has permission to access a resource.
    
    Args:
        user_role: The user's role
        user_tenant_id: The user's tenant ID
        resource_tenant_id: The tenant ID of the resource
        permission: The required permission
    
    Returns:
        True if access is granted, False otherwise
    """
    # Check if user has the required permission
    if not check_permission(user_role, permission):
        return False
    
    # Check tenant isolation - users can only access resources in their tenant
    return user_tenant_id == resource_tenant_id


def check_user_management_access(
    manager_role: UserRole,
    manager_tenant_id: str,
    target_user_tenant_id: str,
    target_user_role: UserRole,
    action: Permission
) -> bool:
    """
    Check if a user can perform management actions on another user.
    
    Args:
        manager_role: The role of the user performing the action
        manager_tenant_id: The tenant ID of the manager
        target_user_tenant_id: The tenant ID of the target user
        target_user_role: The role of the target user
        action: The management action being performed
    
    Returns:
        True if the action is allowed, False otherwise
    """
    # Check if manager has the required permission
    if not check_permission(manager_role, action):
        return False
    
    # Check tenant isolation
    if manager_tenant_id != target_user_tenant_id:
        return False
    
    # For role assignment, check if manager can assign the target role
    if action == Permission.USER_ROLE_ASSIGN:
        return rbac_manager.can_assign_role(manager_role, target_user_role)
    
    # For other user management actions, check role hierarchy
    role_hierarchy = {
        UserRole.CREATOR: 1,
        UserRole.MEMBER: 2,
        UserRole.ADMIN: 3,
    }
    
    manager_level = role_hierarchy.get(manager_role, 0)
    target_level = role_hierarchy.get(target_user_role, 0)
    
    # Managers can only manage users with equal or lower roles
    return manager_level >= target_level