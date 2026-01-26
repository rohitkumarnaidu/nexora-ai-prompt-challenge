"""
Configuration management for Nexora AI Platform.

This module handles environment variables and configuration settings
for different deployment stages.
"""

import os
from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Environment
    stage: str = Field(default="dev", env="STAGE")
    aws_region: str = Field(default="us-east-1", env="AWS_DEFAULT_REGION")
    
    # Database Tables
    users_table: str = Field(default="nexora-users-dev", env="USERS_TABLE")
    tenants_table: str = Field(default="nexora-tenants-dev", env="TENANTS_TABLE")
    content_requests_table: str = Field(default="nexora-content-requests-dev", env="CONTENT_REQUESTS_TABLE")
    generated_content_table: str = Field(default="nexora-generated-content-dev", env="GENERATED_CONTENT_TABLE")
    workflow_executions_table: str = Field(default="nexora-workflow-executions-dev", env="WORKFLOW_EXECUTIONS_TABLE")
    publications_table: str = Field(default="nexora-publications-dev", env="PUBLICATIONS_TABLE")
    
    # Storage
    content_bucket: str = Field(default="nexora-content-dev", env="CONTENT_BUCKET")
    analytics_bucket: str = Field(default="nexora-analytics-dev", env="ANALYTICS_BUCKET")
    
    # OpenSearch
    opensearch_endpoint: str = Field(default="http://localhost:4566", env="OPENSEARCH_ENDPOINT")
    opensearch_index_documents: str = "documents"
    opensearch_index_content: str = "content"
    
    # Redis (optional)
    redis_endpoint: Optional[str] = Field(default=None, env="REDIS_ENDPOINT")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    
    # Cognito
    user_pool_id: Optional[str] = Field(default=None, env="USER_POOL_ID")
    user_pool_client_id: Optional[str] = Field(default=None, env="USER_POOL_CLIENT_ID")
    cognito_domain: Optional[str] = Field(default=None, env="COGNITO_DOMAIN")
    
    # AI Configuration
    bedrock_region: str = Field(default="us-east-1", env="BEDROCK_REGION")
    default_embedding_model: str = Field(
        default="amazon.titan-embed-text-v1", 
        env="DEFAULT_EMBEDDING_MODEL"
    )
    default_text_model: str = Field(
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        env="DEFAULT_TEXT_MODEL"
    )
    max_tokens: int = Field(default=4000, env="MAX_TOKENS")
    temperature: float = Field(default=0.7, env="TEMPERATURE")
    
    # Rate Limiting
    rate_limit_requests_per_minute: int = Field(default=60, env="RATE_LIMIT_RPM")
    rate_limit_tokens_per_minute: int = Field(default=10000, env="RATE_LIMIT_TPM")
    
    # Content Generation
    max_content_length: int = Field(default=10000, env="MAX_CONTENT_LENGTH")
    default_chunk_size: int = Field(default=1000, env="DEFAULT_CHUNK_SIZE")
    default_chunk_overlap: int = Field(default=200, env="DEFAULT_CHUNK_OVERLAP")
    
    # Publishing
    webhook_timeout_seconds: int = Field(default=30, env="WEBHOOK_TIMEOUT")
    max_retry_attempts: int = Field(default=3, env="MAX_RETRY_ATTEMPTS")
    
    # Analytics
    analytics_batch_size: int = Field(default=100, env="ANALYTICS_BATCH_SIZE")
    metrics_retention_days: int = Field(default=90, env="METRICS_RETENTION_DAYS")
    
    # Security
    jwt_secret_key: Optional[str] = Field(default=None, env="JWT_SECRET_KEY")
    jwt_access_token_expire_minutes: int = Field(default=60, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=30, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    encryption_key: Optional[str] = Field(default=None, env="ENCRYPTION_KEY")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    enable_debug: bool = Field(default=False, env="ENABLE_DEBUG")
    
    # Feature Flags
    enable_responsible_ai: bool = Field(default=True, env="ENABLE_RESPONSIBLE_AI")
    enable_analytics: bool = Field(default=True, env="ENABLE_ANALYTICS")
    enable_caching: bool = Field(default=True, env="ENABLE_CACHING")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class LocalStackSettings(BaseSettings):
    """LocalStack-specific settings for local development."""
    
    localstack_endpoint: str = Field(default="http://localhost:4566", env="LOCALSTACK_ENDPOINT")
    use_localstack: bool = Field(default=False, env="USE_LOCALSTACK")
    
    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()
localstack_settings = LocalStackSettings()


def get_aws_config() -> Dict[str, Any]:
    """Get AWS configuration based on environment."""
    config = {
        "region_name": settings.aws_region,
    }
    
    if localstack_settings.use_localstack:
        config.update({
            "endpoint_url": localstack_settings.localstack_endpoint,
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
        })
    
    return config


def get_bedrock_config() -> Dict[str, Any]:
    """Get Bedrock-specific configuration."""
    return {
        "region_name": settings.bedrock_region,
        "model_id": settings.default_text_model,
        "embedding_model_id": settings.default_embedding_model,
        "max_tokens": settings.max_tokens,
        "temperature": settings.temperature,
    }


def get_opensearch_config() -> Dict[str, str]:
    """Get OpenSearch configuration."""
    return {
        "endpoint": settings.opensearch_endpoint,
        "documents_index": settings.opensearch_index_documents,
        "content_index": settings.opensearch_index_content,
    }


def get_redis_config() -> Optional[Dict[str, Any]]:
    """Get Redis configuration if available."""
    if not settings.redis_endpoint:
        return None
    
    return {
        "host": settings.redis_endpoint,
        "port": settings.redis_port,
        "decode_responses": True,
    }


def is_development() -> bool:
    """Check if running in development environment."""
    return settings.stage in ["dev", "development", "local"]


def is_production() -> bool:
    """Check if running in production environment."""
    return settings.stage in ["prod", "production"]