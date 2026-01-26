"""
Unit tests for RBAC (Role-Based Access Control) system.
"""

import pytest
from unittest.mock import Mock, patch

from ...shared.models import UserRole
from ...shared.rbac import (
    Permission,
    RBACManager,
    rbac_manager,
    check_permission,
    check_any_permission,
    check_all_permissions,
    check_resource_access,
    check_user_management_access,
)


class TestRBACManager:
    """Test cases for RBACManager."""
    
    def test_get_role_permissions_creator(self):
        """Test getting permissions for CREATOR role."""
        permissions = rbac_manager.get_role_permissions(UserRole.CREATOR)
        
        #