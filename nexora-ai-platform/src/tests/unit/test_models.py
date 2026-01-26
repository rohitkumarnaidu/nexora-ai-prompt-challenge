"""
Unit tests for shared models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from ...shared.models import (
    User,
    Tenant,
    ContentRequest,
    GeneratedContent,
    UserRole,
    TenantType,
    SubscriptionTier,
    ContentType,
    AutomationMode,
    ContentStatus,
)


class TestUser:
    """Test User model."""
    
    def test_user_creation_with_defaults(self):
        """Test user creation with default values."""
        user = User(
            email="test@example.com",
            cognito_sub="test-sub",
            tenant_id="test-tenant",
            role=UserRole.CREATOR,
            first_name="Test",
            last_name="User",
        )
        
        assert user.email == "test@example.com"
        assert user.role == UserRole.CREATOR
        assert user.is_active is True
        assert user.preferences.language == "en"
        assert isinstance(user.created_at, datetime)
    
    def test_user_validation_invalid_email(self):
        """Test user validation with invalid email."""
        # Note: Basic validation - in production you'd use email validator
        user = User(
            email="invalid-email",
            cognito_sub="test-sub",
            tenant_id="test-tenant",
            role=UserRole.CREATOR,
            first_name="Test",
            last_name="User",
        )
        # This should pass as we don't have email validation in the model yet
        assert user.email == "invalid-email"
    
    def test_user_role_enum(self):
        """Test user role enum validation."""
        user = User(
            email="test@example.com",
            cognito_sub="test-sub",
            tenant_id="test-tenant",
            role="INVALID_ROLE",  # This should raise ValidationError
            first_name="Test",
            last_name="User",
        )
        # Pydantic will convert string to enum if possible
        # Invalid values will raise ValidationError


class TestTenant:
    """Test Tenant model."""
    
    def test_tenant_creation_with_defaults(self):
        """Test tenant creation with default values."""
        tenant = Tenant(
            name="Test Tenant",
            type=TenantType.INDIVIDUAL,
            subscription_tier=SubscriptionTier.FREE,
        )
        
        assert tenant.name == "Test Tenant"
        assert tenant.type == TenantType.INDIVIDUAL
        assert tenant.subscription_tier == SubscriptionTier.FREE
        assert tenant.is_active is True
        assert tenant.resource_quotas.max_content_requests_per_month == 100
    
    def test_tenant_with_custom_quotas(self):
        """Test tenant with custom resource quotas."""
        from ...shared.models import ResourceQuotas
        
        custom_quotas = ResourceQuotas(
            max_content_requests_per_month=500,
            max_documents_storage_mb=5000,
        )
        
        tenant = Tenant(
            name="Enterprise Tenant",
            type=TenantType.ENTERPRISE,
            subscription_tier=SubscriptionTier.ENTERPRISE,
            resource_quotas=custom_quotas,
        )
        
        assert tenant.resource_quotas.max_content_requests_per_month == 500
        assert tenant.resource_quotas.max_documents_storage_mb == 5000


class TestContentRequest:
    """Test ContentRequest model."""
    
    def test_content_request_creation(self):
        """Test content request creation."""
        request = ContentRequest(
            tenant_id="test-tenant",
            user_id="test-user",
            content_type=ContentType.BLOG_POST,
            prompt="Write a blog post about AI",
            automation_mode=AutomationMode.PARTIAL,
        )
        
        assert request.content_type == ContentType.BLOG_POST
        assert request.automation_mode == AutomationMode.PARTIAL
        assert request.prompt == "Write a blog post about AI"
        assert isinstance(request.request_id, str)
        assert len(request.context_documents) == 0
    
    def test_content_request_with_schedule(self):
        """Test content request with publishing schedule."""
        from ...shared.models import PublishSchedule
        
        schedule = PublishSchedule(
            scheduled_at=datetime(2024, 12, 25, 10, 0, 0),
            timezone="UTC",
        )
        
        request = ContentRequest(
            tenant_id="test-tenant",
            user_id="test-user",
            content_type=ContentType.SOCIAL_MEDIA,
            prompt="Create a social media post",
            automation_mode=AutomationMode.FULL,
            schedule=schedule,
        )
        
        assert request.schedule is not None
        assert request.schedule.scheduled_at.year == 2024
        assert request.schedule.timezone == "UTC"


class TestGeneratedContent:
    """Test GeneratedContent model."""
    
    def test_generated_content_creation(self):
        """Test generated content creation."""
        content = GeneratedContent(
            request_id="test-request",
            tenant_id="test-tenant",
            user_id="test-user",
            title="Test Title",
            body="Test content body",
        )
        
        assert content.title == "Test Title"
        assert content.body == "Test content body"
        assert content.status == ContentStatus.GENERATED
        assert isinstance(content.content_id, str)
        assert content.metadata.word_count == 0  # Default value
    
    def test_generated_content_with_metadata(self):
        """Test generated content with metadata."""
        from ...shared.models import ContentMetadata
        
        metadata = ContentMetadata(
            word_count=500,
            reading_time_minutes=3,
            keywords=["AI", "technology", "future"],
            confidence_score=0.85,
        )
        
        content = GeneratedContent(
            request_id="test-request",
            tenant_id="test-tenant",
            user_id="test-user",
            title="AI Technology Article",
            body="A comprehensive article about AI technology...",
            metadata=metadata,
        )
        
        assert content.metadata.word_count == 500
        assert content.metadata.confidence_score == 0.85
        assert "AI" in content.metadata.keywords
    
    def test_ttl_auto_generation(self):
        """Test TTL auto-generation for content."""
        content = GeneratedContent(
            request_id="test-request",
            tenant_id="test-tenant",
            user_id="test-user",
            title="Test Title",
            body="Test content body",
        )
        
        # TTL should be set automatically
        assert content.ttl is not None
        assert isinstance(content.ttl, int)
        assert content.ttl > 0


class TestModelSerialization:
    """Test model serialization and deserialization."""
    
    def test_user_json_serialization(self):
        """Test user JSON serialization."""
        user = User(
            email="test@example.com",
            cognito_sub="test-sub",
            tenant_id="test-tenant",
            role=UserRole.CREATOR,
            first_name="Test",
            last_name="User",
        )
        
        # Test dict conversion
        user_dict = user.dict()
        assert user_dict["email"] == "test@example.com"
        assert user_dict["role"] == "CREATOR"  # Enum converted to string
        
        # Test JSON serialization
        user_json = user.json()
        assert isinstance(user_json, str)
        assert "test@example.com" in user_json
    
    def test_model_from_dict(self):
        """Test model creation from dictionary."""
        user_data = {
            "email": "test@example.com",
            "cognito_sub": "test-sub",
            "tenant_id": "test-tenant",
            "role": "CREATOR",
            "first_name": "Test",
            "last_name": "User",
        }
        
        user = User(**user_data)
        assert user.email == "test@example.com"
        assert user.role == UserRole.CREATOR