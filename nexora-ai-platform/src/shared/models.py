"""
Shared data models for Nexora AI Platform.

This module contains Pydantic models that define the data structures
used throughout the application.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
import uuid


class UserRole(str, Enum):
    """User roles in the system."""
    CREATOR = "CREATOR"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class TenantType(str, Enum):
    """Types of tenants."""
    INDIVIDUAL = "INDIVIDUAL"
    BUSINESS = "BUSINESS"
    ENTERPRISE = "ENTERPRISE"


class SubscriptionTier(str, Enum):
    """Subscription tiers."""
    FREE = "FREE"
    BASIC = "BASIC"
    PROFESSIONAL = "PROFESSIONAL"
    ENTERPRISE = "ENTERPRISE"


class ContentType(str, Enum):
    """Types of content that can be generated."""
    BLOG_POST = "BLOG_POST"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    EMAIL = "EMAIL"
    MARKETING_COPY = "MARKETING_COPY"
    PRODUCT_DESCRIPTION = "PRODUCT_DESCRIPTION"
    PRESS_RELEASE = "PRESS_RELEASE"


class AutomationMode(str, Enum):
    """Automation modes for content workflows."""
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    MANUAL = "MANUAL"


class ContentStatus(str, Enum):
    """Status of generated content."""
    GENERATED = "GENERATED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class WorkflowState(str, Enum):
    """States in the workflow state machine."""
    CONTENT_REQUEST = "CONTENT_REQUEST"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class ReviewStatus(str, Enum):
    """Status of human reviews."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PublicationStatus(str, Enum):
    """Status of content publications."""
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


# Base Models

class BaseEntity(BaseModel):
    """Base model for all entities."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# User and Tenant Models

class UserPreferences(BaseModel):
    """User preferences and settings."""
    language: str = "en"
    timezone: str = "UTC"
    email_notifications: bool = True
    content_sensitivity_level: str = "medium"
    default_automation_mode: AutomationMode = AutomationMode.PARTIAL


class User(BaseEntity):
    """User model."""
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    cognito_sub: str
    tenant_id: str
    role: UserRole
    first_name: str
    last_name: str
    last_login: Optional[datetime] = None
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    is_active: bool = True


class ResourceQuotas(BaseModel):
    """Resource quotas for tenants."""
    max_content_requests_per_month: int = 100
    max_documents_storage_mb: int = 1000
    max_generated_content_storage_mb: int = 5000
    max_publishing_endpoints: int = 5
    max_team_members: int = 1
    ai_generation_tokens_per_month: int = 100000


class TenantSettings(BaseModel):
    """Tenant-specific settings."""
    default_automation_mode: AutomationMode = AutomationMode.PARTIAL
    require_human_review: bool = True
    content_retention_days: int = 90
    enable_analytics: bool = True
    webhook_url: Optional[str] = None


class Tenant(BaseEntity):
    """Tenant model."""
    tenant_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: TenantType
    subscription_tier: SubscriptionTier
    resource_quotas: ResourceQuotas = Field(default_factory=ResourceQuotas)
    settings: TenantSettings = Field(default_factory=TenantSettings)
    is_active: bool = True


# Content Models

class ContentMetadata(BaseModel):
    """Metadata for generated content."""
    word_count: int = 0
    reading_time_minutes: int = 0
    keywords: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    sentiment_score: Optional[float] = None
    confidence_score: float = 0.0
    model_used: str = ""
    generation_time_seconds: float = 0.0


class PublishSchedule(BaseModel):
    """Publishing schedule configuration."""
    scheduled_at: datetime
    timezone: str = "UTC"
    recurring: bool = False
    recurring_pattern: Optional[str] = None  # cron expression


class ContentRequest(BaseEntity):
    """Content generation request."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    user_id: str
    content_type: ContentType
    title: Optional[str] = None
    prompt: str
    context_documents: List[str] = Field(default_factory=list)
    automation_mode: AutomationMode
    target_endpoints: List[str] = Field(default_factory=list)
    schedule: Optional[PublishSchedule] = None
    additional_instructions: Optional[str] = None
    max_words: Optional[int] = None
    tone: Optional[str] = None
    target_audience: Optional[str] = None


class GeneratedContent(BaseEntity):
    """Generated content model."""
    content_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    tenant_id: str
    user_id: str
    title: str
    body: str
    metadata: ContentMetadata = Field(default_factory=ContentMetadata)
    source_documents: List[str] = Field(default_factory=list)
    status: ContentStatus = ContentStatus.GENERATED
    review_feedback: Optional[str] = None
    ttl: Optional[int] = None  # TTL for DynamoDB

    @validator('ttl', pre=True, always=True)
    def set_ttl(cls, v, values):
        """Set TTL to 90 days from creation."""
        if v is None:
            created_at = values.get('created_at', datetime.utcnow())
            return int((created_at.timestamp() + (90 * 24 * 60 * 60)))
        return v


# Document Models

class DocumentMetadata(BaseModel):
    """Metadata for uploaded documents."""
    file_name: str
    file_size_bytes: int
    file_type: str
    language: str = "en"
    page_count: Optional[int] = None
    word_count: int = 0
    processing_status: str = "pending"
    error_message: Optional[str] = None


class Document(BaseEntity):
    """Document model for RAG pipeline."""
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    user_id: str
    title: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: DocumentMetadata
    s3_key: str
    is_processed: bool = False


# Workflow Models

class WorkflowStep(BaseModel):
    """Individual step in a workflow."""
    step_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowExecution(BaseEntity):
    """Workflow execution tracking."""
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    tenant_id: str
    user_id: str
    current_state: WorkflowState
    automation_mode: AutomationMode
    steps_completed: List[WorkflowStep] = Field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewDecision(BaseModel):
    """Human review decision."""
    decision: ReviewStatus
    feedback: Optional[str] = None
    content_modifications: Optional[Dict[str, Any]] = None


class ReviewRequest(BaseEntity):
    """Human review request."""
    review_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content_id: str
    tenant_id: str
    reviewer_id: str
    status: ReviewStatus = ReviewStatus.PENDING
    feedback: Optional[str] = None
    decision_metadata: Dict[str, Any] = Field(default_factory=dict)
    reviewed_at: Optional[datetime] = None


# Publishing Models

class EndpointConfig(BaseModel):
    """Publishing endpoint configuration."""
    endpoint_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    platform: str  # twitter, linkedin, facebook, wordpress, etc.
    endpoint_type: str  # api, webhook, etc.
    credentials: Dict[str, str] = Field(default_factory=dict)
    settings: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class PublicationRecord(BaseEntity):
    """Record of content publication."""
    publication_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content_id: str
    tenant_id: str
    endpoint_id: str
    status: PublicationStatus
    published_at: Optional[datetime] = None
    external_id: Optional[str] = None
    external_url: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Analytics Models

class AnalyticsEvent(BaseModel):
    """Analytics event model."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    user_id: Optional[str] = None
    event_type: str
    event_data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None


class UsageMetrics(BaseModel):
    """Usage metrics for analytics."""
    tenant_id: str
    period_start: datetime
    period_end: datetime
    content_generated_count: int = 0
    content_published_count: int = 0
    api_requests_count: int = 0
    storage_used_mb: float = 0.0
    ai_tokens_used: int = 0
    active_users_count: int = 0


# API Response Models

class APIResponse(BaseModel):
    """Standard API response format."""
    success: bool
    message: str
    data: Optional[Any] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel):
    """Paginated API response format."""
    items: List[Any]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool