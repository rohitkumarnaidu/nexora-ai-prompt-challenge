"""
Role Management service Lambda handler.

Handles role assignments, user management, and RBAC operations.
"""

import json
from typing import Dict, Any, List, Optional
import structlog
from botocore.exceptions import ClientError

from ...shared.models import User, UserRole, Tenant
from ...shared.utils import (
    create_api_response,
    parse_lambda_event,
    get_correlation_id,
    get_dynamodb_resource,
    handle_aws_error,
    utc_now,
)
from ...shared.config import settings
from ...shared.auth_middleware import (
    require_user_management,
    require_tenant_management,
    get_user_info_from_event,
    get_user_id_from_event,
    get_tenant_id_from_event,
    get_user_role_from_event,
)
from ...shared.rbac import (
    rbac_manager,
    Permission,
    check_user_management_access,
    UserRole as RBACUserRole,
)

logger = structlog.get_logger()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for role management service."""
    correlation_id = get_correlation_id(event)
    logger.info("Role management request received", correlation_id=correlation_id)
    
    try:
        # Parse event
        parsed_event = parse_lambda_event(event)
        http_method = parsed_event["http_method"]
        path = parsed_event["path"]
        body = parsed_event["body"]
        path_params = parsed_event.get("path_parameters", {})
        
        # Route to appropriate handler
        if http_method == "GET":
            if path.endswith("/roles"):
                return handle_list_roles(event, correlation_id)
            elif path.endswith("/users"):
                return handle_list_users(event, correlation_id)
            elif "/users/" in path and path.endswith("/role"):
                user_id = path_params.get("user_id")
                return handle_get_user_role(event, user_id, correlation_id)
            elif "/roles/" in path and path.endswith("/permissions"):
                role_name = path_params.get("role_name")
                return handle_get_role_permissions(event, role_name, correlation_id)
        
        elif http_method == "POST":
            if path.endswith("/users/invite"):
                return handle_invite_user(event, body, correlation_id)
            elif "/users/" in path and path.endswith("/role"):
                user_id = path_params.get("user_id")
                return handle_assign_role(event, user_id, body, correlation_id)
        
        elif http_method == "PUT":
            if "/users/" in path:
                user_id = path_params.get("user_id")
                return handle_update_user(event, user_id, body, correlation_id)
        
        elif http_method == "DELETE":
            if "/users/" in path:
                user_id = path_params.get("user_id")
                return handle_delete_user(event, user_id, correlation_id)
        
        return create_api_response(
            success=False,
            message="Invalid request",
            error_code="INVALID_REQUEST",
            status_code=400,
        )
        
    except Exception as e:
        logger.error("Role management error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Internal server error",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )


@require_user_management("read")
def handle_list_roles(event: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """List all available roles and their permissions."""
    try:
        user_role = get_user_role_from_event(event)
        
        # Get all role definitions
        role_definitions = rbac_manager.list_all_roles()
        
        # Format response
        roles_data = []
        for role_def in role_definitions:
            permissions = rbac_manager.get_role_permissions(role_def.name)
            
            roles_data.append({
                "name": role_def.name.value,
                "description": role_def.description,
                "permissions": [perm.value for perm in permissions],
                "inherits_from": role_def.inherits_from.value if role_def.inherits_from else None,
                "can_assign": rbac_manager.can_assign_role(UserRole(user_role), role_def.name)
            })
        
        return create_api_response(
            success=True,
            message="Roles retrieved successfully",
            data={"roles": roles_data},
        )
        
    except Exception as e:
        logger.error("List roles error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Failed to retrieve roles",
            error_code="LIST_ROLES_FAILED",
            status_code=500,
        )


@require_user_management("read")
def handle_list_users(event: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """List users in the tenant."""
    try:
        tenant_id = get_tenant_id_from_event(event)
        
        # Get users from DynamoDB
        dynamodb = get_dynamodb_resource()
        users_table = dynamodb.Table(settings.users_table)
        
        # Query users by tenant_id (assuming GSI exists)
        response = users_table.query(
            IndexName="tenant-id-index",
            KeyConditionExpression="tenant_id = :tenant_id",
            ExpressionAttributeValues={":tenant_id": tenant_id}
        )
        
        users_data = []
        for user_item in response["Items"]:
            users_data.append({
                "user_id": user_item["user_id"],
                "email": user_item["email"],
                "first_name": user_item["first_name"],
                "last_name": user_item["last_name"],
                "role": user_item["role"],
                "is_active": user_item.get("is_active", True),
                "created_at": user_item["created_at"],
                "last_login": user_item.get("last_login"),
            })
        
        return create_api_response(
            success=True,
            message="Users retrieved successfully",
            data={"users": users_data},
        )
        
    except Exception as e:
        logger.error("List users error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Failed to retrieve users",
            error_code="LIST_USERS_FAILED",
            status_code=500,
        )


@require_user_management("read")
def handle_get_user_role(event: Dict[str, Any], user_id: str, correlation_id: str) -> Dict[str, Any]:
    """Get role information for a specific user."""
    try:
        tenant_id = get_tenant_id_from_event(event)
        
        if not user_id:
            return create_api_response(
                success=False,
                message="User ID is required",
                error_code="MISSING_USER_ID",
                status_code=400,
            )
        
        # Get user from DynamoDB
        dynamodb = get_dynamodb_resource()
        users_table = dynamodb.Table(settings.users_table)
        
        response = users_table.get_item(Key={"user_id": user_id})
        
        if "Item" not in response:
            return create_api_response(
                success=False,
                message="User not found",
                error_code="USER_NOT_FOUND",
                status_code=404,
            )
        
        user_data = response["Item"]
        
        # Check tenant access
        if user_data["tenant_id"] != tenant_id:
            return create_api_response(
                success=False,
                message="Access denied to user",
                error_code="USER_ACCESS_DENIED",
                status_code=403,
            )
        
        # Get role permissions
        user_role = UserRole(user_data["role"])
        permissions = rbac_manager.get_role_permissions(user_role)
        
        return create_api_response(
            success=True,
            message="User role retrieved successfully",
            data={
                "user_id": user_id,
                "role": user_data["role"],
                "permissions": [perm.value for perm in permissions],
            },
        )
        
    except Exception as e:
        logger.error("Get user role error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Failed to retrieve user role",
            error_code="GET_USER_ROLE_FAILED",
            status_code=500,
        )


def handle_get_role_permissions(event: Dict[str, Any], role_name: str, correlation_id: str) -> Dict[str, Any]:
    """Get permissions for a specific role."""
    try:
        if not role_name:
            return create_api_response(
                success=False,
                message="Role name is required",
                error_code="MISSING_ROLE_NAME",
                status_code=400,
            )
        
        try:
            role = UserRole(role_name.upper())
        except ValueError:
            return create_api_response(
                success=False,
                message=f"Invalid role: {role_name}",
                error_code="INVALID_ROLE",
                status_code=400,
            )
        
        # Get role definition and permissions
        role_def = rbac_manager.get_role_definition(role)
        if not role_def:
            return create_api_response(
                success=False,
                message=f"Role definition not found: {role_name}",
                error_code="ROLE_NOT_FOUND",
                status_code=404,
            )
        
        permissions = rbac_manager.get_role_permissions(role)
        
        return create_api_response(
            success=True,
            message="Role permissions retrieved successfully",
            data={
                "role": role_def.name.value,
                "description": role_def.description,
                "permissions": [perm.value for perm in permissions],
                "inherits_from": role_def.inherits_from.value if role_def.inherits_from else None,
            },
        )
        
    except Exception as e:
        logger.error("Get role permissions error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Failed to retrieve role permissions",
            error_code="GET_ROLE_PERMISSIONS_FAILED",
            status_code=500,
        )


@require_user_management("invite")
def handle_invite_user(event: Dict[str, Any], body: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Invite a new user to the tenant."""
    try:
        tenant_id = get_tenant_id_from_event(event)
        inviter_role = get_user_role_from_event(event)
        
        # Extract invitation data
        email = body.get("email")
        role = body.get("role", "CREATOR")
        first_name = body.get("first_name")
        last_name = body.get("last_name")
        
        if not all([email, first_name, last_name]):
            return create_api_response(
                success=False,
                message="Missing required fields: email, first_name, last_name",
                error_code="MISSING_FIELDS",
                status_code=400,
            )
        
        # Validate role
        try:
            target_role = UserRole(role)
        except ValueError:
            return create_api_response(
                success=False,
                message=f"Invalid role: {role}",
                error_code="INVALID_ROLE",
                status_code=400,
            )
        
        # Check if inviter can assign this role
        inviter_role_enum = UserRole(inviter_role)
        if not rbac_manager.can_assign_role(inviter_role_enum, target_role):
            return create_api_response(
                success=False,
                message=f"Cannot assign role {role}. Insufficient permissions.",
                error_code="CANNOT_ASSIGN_ROLE",
                status_code=403,
            )
        
        # Check if user already exists
        dynamodb = get_dynamodb_resource()
        users_table = dynamodb.Table(settings.users_table)
        
        # Scan for existing user with same email (in production, use GSI)
        response = users_table.scan(
            FilterExpression="email = :email",
            ExpressionAttributeValues={":email": email}
        )
        
        if response["Items"]:
            return create_api_response(
                success=False,
                message="User with this email already exists",
                error_code="USER_EXISTS",
                status_code=409,
            )
        
        # Create user record (invitation pending)
        user = User(
            email=email,
            cognito_sub="",  # Will be set when user completes registration
            tenant_id=tenant_id,
            role=target_role,
            first_name=first_name,
            last_name=last_name,
            is_active=False,  # Inactive until they complete registration
        )
        
        # Save user
        users_table.put_item(Item=user.dict())
        
        # TODO: Send invitation email (would integrate with SES)
        
        logger.info(
            "User invitation created",
            user_id=user.user_id,
            email=email,
            role=role,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        
        return create_api_response(
            success=True,
            message="User invitation sent successfully",
            data={
                "user_id": user.user_id,
                "email": email,
                "role": role,
                "status": "invitation_sent",
            },
        )
        
    except Exception as e:
        logger.error("Invite user error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Failed to invite user",
            error_code="INVITE_USER_FAILED",
            status_code=500,
        )


@require_user_management("assign_role")
def handle_assign_role(event: Dict[str, Any], user_id: str, body: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Assign a role to a user."""
    try:
        tenant_id = get_tenant_id_from_event(event)
        assigner_role = get_user_role_from_event(event)
        
        if not user_id:
            return create_api_response(
                success=False,
                message="User ID is required",
                error_code="MISSING_USER_ID",
                status_code=400,
            )
        
        new_role = body.get("role")
        if not new_role:
            return create_api_response(
                success=False,
                message="Role is required",
                error_code="MISSING_ROLE",
                status_code=400,
            )
        
        # Validate role
        try:
            target_role = UserRole(new_role)
        except ValueError:
            return create_api_response(
                success=False,
                message=f"Invalid role: {new_role}",
                error_code="INVALID_ROLE",
                status_code=400,
            )
        
        # Get target user
        dynamodb = get_dynamodb_resource()
        users_table = dynamodb.Table(settings.users_table)
        
        response = users_table.get_item(Key={"user_id": user_id})
        
        if "Item" not in response:
            return create_api_response(
                success=False,
                message="User not found",
                error_code="USER_NOT_FOUND",
                status_code=404,
            )
        
        user_data = response["Item"]
        
        # Check tenant access
        if user_data["tenant_id"] != tenant_id:
            return create_api_response(
                success=False,
                message="Access denied to user",
                error_code="USER_ACCESS_DENIED",
                status_code=403,
            )
        
        # Check if assigner can assign this role
        current_user_role = UserRole(user_data["role"])
        assigner_role_enum = UserRole(assigner_role)
        
        if not check_user_management_access(
            assigner_role_enum,
            tenant_id,
            user_data["tenant_id"],
            current_user_role,
            Permission.USER_ROLE_ASSIGN
        ):
            return create_api_response(
                success=False,
                message="Insufficient permissions to assign role",
                error_code="INSUFFICIENT_PERMISSIONS",
                status_code=403,
            )
        
        if not rbac_manager.can_assign_role(assigner_role_enum, target_role):
            return create_api_response(
                success=False,
                message=f"Cannot assign role {new_role}. Insufficient permissions.",
                error_code="CANNOT_ASSIGN_ROLE",
                status_code=403,
            )
        
        # Update user role
        users_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET #role = :role, updated_at = :timestamp",
            ExpressionAttributeNames={"#role": "role"},
            ExpressionAttributeValues={
                ":role": target_role.value,
                ":timestamp": utc_now().isoformat(),
            },
        )
        
        logger.info(
            "User role assigned",
            user_id=user_id,
            old_role=user_data["role"],
            new_role=new_role,
            assigner_role=assigner_role,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        
        return create_api_response(
            success=True,
            message="Role assigned successfully",
            data={
                "user_id": user_id,
                "old_role": user_data["role"],
                "new_role": new_role,
            },
        )
        
    except Exception as e:
        logger.error("Assign role error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Failed to assign role",
            error_code="ASSIGN_ROLE_FAILED",
            status_code=500,
        )


@require_user_management("update")
def handle_update_user(event: Dict[str, Any], user_id: str, body: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Update user information."""
    try:
        tenant_id = get_tenant_id_from_event(event)
        
        if not user_id:
            return create_api_response(
                success=False,
                message="User ID is required",
                error_code="MISSING_USER_ID",
                status_code=400,
            )
        
        # Get user
        dynamodb = get_dynamodb_resource()
        users_table = dynamodb.Table(settings.users_table)
        
        response = users_table.get_item(Key={"user_id": user_id})
        
        if "Item" not in response:
            return create_api_response(
                success=False,
                message="User not found",
                error_code="USER_NOT_FOUND",
                status_code=404,
            )
        
        user_data = response["Item"]
        
        # Check tenant access
        if user_data["tenant_id"] != tenant_id:
            return create_api_response(
                success=False,
                message="Access denied to user",
                error_code="USER_ACCESS_DENIED",
                status_code=403,
            )
        
        # Build update expression
        update_expression = "SET updated_at = :timestamp"
        expression_values = {":timestamp": utc_now().isoformat()}
        
        # Update allowed fields
        if "first_name" in body:
            update_expression += ", first_name = :first_name"
            expression_values[":first_name"] = body["first_name"]
        
        if "last_name" in body:
            update_expression += ", last_name = :last_name"
            expression_values[":last_name"] = body["last_name"]
        
        if "is_active" in body:
            update_expression += ", is_active = :is_active"
            expression_values[":is_active"] = body["is_active"]
        
        # Update user
        users_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
        )
        
        logger.info(
            "User updated",
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        
        return create_api_response(
            success=True,
            message="User updated successfully",
            data={"user_id": user_id},
        )
        
    except Exception as e:
        logger.error("Update user error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Failed to update user",
            error_code="UPDATE_USER_FAILED",
            status_code=500,
        )


@require_user_management("delete")
def handle_delete_user(event: Dict[str, Any], user_id: str, correlation_id: str) -> Dict[str, Any]:
    """Delete a user (soft delete by deactivating)."""
    try:
        tenant_id = get_tenant_id_from_event(event)
        deleter_role = get_user_role_from_event(event)
        deleter_user_id = get_user_id_from_event(event)
        
        if not user_id:
            return create_api_response(
                success=False,
                message="User ID is required",
                error_code="MISSING_USER_ID",
                status_code=400,
            )
        
        # Prevent self-deletion
        if user_id == deleter_user_id:
            return create_api_response(
                success=False,
                message="Cannot delete your own account",
                error_code="CANNOT_DELETE_SELF",
                status_code=400,
            )
        
        # Get user
        dynamodb = get_dynamodb_resource()
        users_table = dynamodb.Table(settings.users_table)
        
        response = users_table.get_item(Key={"user_id": user_id})
        
        if "Item" not in response:
            return create_api_response(
                success=False,
                message="User not found",
                error_code="USER_NOT_FOUND",
                status_code=404,
            )
        
        user_data = response["Item"]
        
        # Check tenant access
        if user_data["tenant_id"] != tenant_id:
            return create_api_response(
                success=False,
                message="Access denied to user",
                error_code="USER_ACCESS_DENIED",
                status_code=403,
            )
        
        # Check if deleter can delete this user
        target_user_role = UserRole(user_data["role"])
        deleter_role_enum = UserRole(deleter_role)
        
        if not check_user_management_access(
            deleter_role_enum,
            tenant_id,
            user_data["tenant_id"],
            target_user_role,
            Permission.USER_DELETE
        ):
            return create_api_response(
                success=False,
                message="Insufficient permissions to delete user",
                error_code="INSUFFICIENT_PERMISSIONS",
                status_code=403,
            )
        
        # Soft delete by deactivating
        users_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET is_active = :inactive, updated_at = :timestamp",
            ExpressionAttributeValues={
                ":inactive": False,
                ":timestamp": utc_now().isoformat(),
            },
        )
        
        logger.info(
            "User deleted (deactivated)",
            user_id=user_id,
            deleter_role=deleter_role,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        
        return create_api_response(
            success=True,
            message="User deleted successfully",
            data={"user_id": user_id, "status": "deactivated"},
        )
        
    except Exception as e:
        logger.error("Delete user error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Failed to delete user",
            error_code="DELETE_USER_FAILED",
            status_code=500,
        )