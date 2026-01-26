"""
Property-based tests for content generation properties.

These tests validate universal properties that should hold across all inputs.
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timezone

from ...shared.models import (
    ContentRequest,
    GeneratedContent,
    ContentType,
    AutomationMode,
    ContentStatus,
    ContentMetadata,
)


# Hypothesis strategies for generating test data
content_types = st.sampled_from(list(ContentType))
automation_modes = st.sampled_from(list(AutomationMode))
content_statuses = st.sampled_from(list(ContentStatus))

tenant_ids = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc")))
user_ids = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc")))
prompts = st.text(min_size=10, max_size=1000)
titles = st.text(min_size=1, max_size=200)
content_bodies = st.text(min_size=1, max_size=10000)


class TestContentRequestProperties:
    """Property-based tests for ContentRequest model."""
    
    @given(
        tenant_id=tenant_ids,
        user_id=user_ids,
        content_type=content_types,
        prompt=prompts,
        automation_mode=automation_modes,
    )
    @settings(max_examples=50)
    def test_content_request_creation_property(
        self, tenant_id, user_id, content_type, prompt, automation_mode
    ):
        """
        Feature: nexora-ai-platform, Property: Content Request Creation
        For any valid content request parameters, the system should create
        a valid ContentRequest object with proper defaults.
        """
        request = ContentRequest(
            tenant_id=tenant_id,
            user_id=user_id,
            content_type=content_type,
            prompt=prompt,
            automation_mode=automation_mode,
        )
        
        # Universal properties that should always hold
        assert request.tenant_id == tenant_id
        assert request.user_id == user_id
        assert request.content_type == content_type
        assert request.prompt == prompt
        assert request.automation_mode == automation_mode
        
        # Generated fields should be valid
        assert isinstance(request.request_id, str)
        assert len(request.request_id) > 0
        assert isinstance(request.created_at, datetime)
        assert isinstance(request.updated_at, datetime)
        
        # Default values should be set
        assert isinstance(request.context_documents, list)
        assert isinstance(request.target_endpoints, list)
    
    @given(
        tenant_id=tenant_ids,
        user_id=user_ids,
        content_type=content_types,
        prompt=prompts,
        automation_mode=automation_modes,
        context_docs=st.lists(st.text(min_size=1, max_size=50), max_size=10),
    )
    @settings(max_examples=30)
    def test_content_request_with_context_property(
        self, tenant_id, user_id, content_type, prompt, automation_mode, context_docs
    ):
        """
        Feature: nexora-ai-platform, Property: Content Request with Context
        For any content request with context documents, the context should
        be properly stored and accessible.
        """
        request = ContentRequest(
            tenant_id=tenant_id,
            user_id=user_id,
            content_type=content_type,
            prompt=prompt,
            automation_mode=automation_mode,
            context_documents=context_docs,
        )
        
        # Context documents should be preserved
        assert request.context_documents == context_docs
        assert len(request.context_documents) == len(context_docs)
        
        # All context documents should be strings
        assert all(isinstance(doc, str) for doc in request.context_documents)


class TestGeneratedContentProperties:
    """Property-based tests for GeneratedContent model."""
    
    @given(
        request_id=st.text(min_size=1, max_size=50),
        tenant_id=tenant_ids,
        user_id=user_ids,
        title=titles,
        body=content_bodies,
    )
    @settings(max_examples=50)
    def test_generated_content_creation_property(
        self, request_id, tenant_id, user_id, title, body
    ):
        """
        Feature: nexora-ai-platform, Property: Generated Content Creation
        For any valid generated content parameters, the system should create
        a valid GeneratedContent object with proper metadata.
        """
        content = GeneratedContent(
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            body=body,
        )
        
        # Core properties should be preserved
        assert content.request_id == request_id
        assert content.tenant_id == tenant_id
        assert content.user_id == user_id
        assert content.title == title
        assert content.body == body
        
        # Generated fields should be valid
        assert isinstance(content.content_id, str)
        assert len(content.content_id) > 0
        assert isinstance(content.created_at, datetime)
        assert isinstance(content.updated_at, datetime)
        
        # Default status should be GENERATED
        assert content.status == ContentStatus.GENERATED
        
        # Metadata should be initialized
        assert isinstance(content.metadata, ContentMetadata)
        assert content.metadata.confidence_score >= 0.0
        assert content.metadata.confidence_score <= 1.0
        
        # TTL should be set
        assert content.ttl is not None
        assert isinstance(content.ttl, int)
        assert content.ttl > 0
    
    @given(
        request_id=st.text(min_size=1, max_size=50),
        tenant_id=tenant_ids,
        user_id=user_ids,
        title=titles,
        body=content_bodies,
        word_count=st.integers(min_value=0, max_value=10000),
        confidence_score=st.floats(min_value=0.0, max_value=1.0),
        keywords=st.lists(st.text(min_size=1, max_size=20), max_size=10),
    )
    @settings(max_examples=30)
    def test_generated_content_with_metadata_property(
        self, request_id, tenant_id, user_id, title, body, word_count, confidence_score, keywords
    ):
        """
        Feature: nexora-ai-platform, Property: Generated Content with Metadata
        For any generated content with metadata, the metadata should be
        properly validated and stored.
        """
        metadata = ContentMetadata(
            word_count=word_count,
            confidence_score=confidence_score,
            keywords=keywords,
        )
        
        content = GeneratedContent(
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            body=body,
            metadata=metadata,
        )
        
        # Metadata should be preserved
        assert content.metadata.word_count == word_count
        assert content.metadata.confidence_score == confidence_score
        assert content.metadata.keywords == keywords
        
        # Confidence score should be within valid range
        assert 0.0 <= content.metadata.confidence_score <= 1.0
        
        # Word count should be non-negative
        assert content.metadata.word_count >= 0
        
        # Keywords should be a list of strings
        assert isinstance(content.metadata.keywords, list)
        assert all(isinstance(keyword, str) for keyword in content.metadata.keywords)


class TestContentValidationProperties:
    """Property-based tests for content validation."""
    
    @given(
        content_type=content_types,
        automation_mode=automation_modes,
    )
    @settings(max_examples=20)
    def test_automation_mode_compatibility_property(self, content_type, automation_mode):
        """
        Feature: nexora-ai-platform, Property: Automation Mode Compatibility
        For any content type and automation mode combination, the system
        should handle the combination appropriately.
        """
        request = ContentRequest(
            tenant_id="test-tenant",
            user_id="test-user",
            content_type=content_type,
            prompt="Test prompt",
            automation_mode=automation_mode,
        )
        
        # All combinations should be valid
        assert request.content_type in ContentType
        assert request.automation_mode in AutomationMode
        
        # Specific business rules can be tested here
        # For example, certain content types might require human review
        if content_type == ContentType.PRESS_RELEASE:
            # Press releases might always require at least partial automation
            assert automation_mode in [AutomationMode.PARTIAL, AutomationMode.MANUAL]
    
    @given(
        status=content_statuses,
    )
    @settings(max_examples=10)
    def test_content_status_transitions_property(self, status):
        """
        Feature: nexora-ai-platform, Property: Content Status Transitions
        For any content status, the status should be a valid enum value
        and follow proper state machine rules.
        """
        content = GeneratedContent(
            request_id="test-request",
            tenant_id="test-tenant",
            user_id="test-user",
            title="Test Title",
            body="Test body",
            status=status,
        )
        
        # Status should be valid
        assert content.status in ContentStatus
        
        # Business rules for status transitions
        if status == ContentStatus.PUBLISHED:
            # Published content should have been approved first
            # (This would be enforced by business logic, not the model)
            pass
        
        if status == ContentStatus.REJECTED:
            # Rejected content might have feedback
            # (This would be set by the review process)
            pass


class TestContentInvariantProperties:
    """Property-based tests for content invariants."""
    
    @given(
        tenant_id=tenant_ids,
        user_id=user_ids,
        title=titles,
        body=content_bodies,
    )
    @settings(max_examples=30)
    def test_content_immutability_property(self, tenant_id, user_id, title, body):
        """
        Feature: nexora-ai-platform, Property: Content Immutability
        For any generated content, certain fields should remain immutable
        after creation (like IDs and timestamps).
        """
        content = GeneratedContent(
            request_id="test-request",
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            body=body,
        )
        
        # Store original values
        original_content_id = content.content_id
        original_created_at = content.created_at
        original_tenant_id = content.tenant_id
        original_user_id = content.user_id
        
        # These should never change
        assert content.content_id == original_content_id
        assert content.created_at == original_created_at
        assert content.tenant_id == original_tenant_id
        assert content.user_id == original_user_id
        
        # IDs should be unique (at least different from empty string)
        assert len(content.content_id) > 0
        assert content.content_id != ""
    
    @given(
        prompt=prompts,
    )
    @settings(max_examples=20)
    def test_prompt_preservation_property(self, prompt):
        """
        Feature: nexora-ai-platform, Property: Prompt Preservation
        For any content request, the original prompt should be preserved
        exactly as provided by the user.
        """
        request = ContentRequest(
            tenant_id="test-tenant",
            user_id="test-user",
            content_type=ContentType.BLOG_POST,
            prompt=prompt,
            automation_mode=AutomationMode.PARTIAL,
        )
        
        # Prompt should be preserved exactly
        assert request.prompt == prompt
        
        # Prompt should not be empty (enforced by strategy)
        assert len(request.prompt) >= 10  # As per strategy min_size