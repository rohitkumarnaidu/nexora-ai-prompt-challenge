"""
Shared utility functions for Nexora AI Platform.

This module contains common utility functions used across the application.
"""

import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
import boto3
from botocore.exceptions import ClientError
import structlog

from .config import settings, get_aws_config

# Configure structured logging
logger = structlog.get_logger()


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    unique_id = str(uuid.uuid4())
    return f"{prefix}{unique_id}" if prefix else unique_id


def generate_short_id(length: int = 8) -> str:
    """Generate a short unique ID."""
    return str(uuid.uuid4()).replace("-", "")[:length]


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def to_iso_string(dt: datetime) -> str:
    """Convert datetime to ISO string."""
    return dt.isoformat()


def from_iso_string(iso_string: str) -> datetime:
    """Convert ISO string to datetime."""
    return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))


def hash_string(text: str) -> str:
    """Generate SHA-256 hash of a string."""
    return hashlib.sha256(text.encode()).hexdigest()


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, "_")
    return filename.strip()


def calculate_reading_time(text: str, words_per_minute: int = 200) -> int:
    """Calculate estimated reading time in minutes."""
    word_count = len(text.split())
    return max(1, round(word_count / words_per_minute))


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract keywords from text (simple implementation)."""
    # This is a basic implementation - in production, you'd use NLP libraries
    words = text.lower().split()
    # Remove common stop words
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "is", "are", "was", "were", "be", "been", "have",
        "has", "had", "do", "does", "did", "will", "would", "could", "should",
        "may", "might", "must", "can", "this", "that", "these", "those"
    }
    
    # Count word frequency
    word_freq = {}
    for word in words:
        word = word.strip(".,!?;:")
        if len(word) > 3 and word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Return top keywords
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_words[:max_keywords]]


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence endings near the chunk boundary
            for i in range(end, max(start + chunk_size // 2, end - 100), -1):
                if text[i] in '.!?':
                    end = i + 1
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap
        if start >= len(text):
            break
    
    return chunks


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def mask_sensitive_data(data: Dict[str, Any], sensitive_keys: List[str] = None) -> Dict[str, Any]:
    """Mask sensitive data in dictionary."""
    if sensitive_keys is None:
        sensitive_keys = ["password", "secret", "key", "token", "credentials"]
    
    masked_data = data.copy()
    for key, value in masked_data.items():
        if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
            if isinstance(value, str) and len(value) > 4:
                masked_data[key] = value[:2] + "*" * (len(value) - 4) + value[-2:]
            else:
                masked_data[key] = "***"
        elif isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value, sensitive_keys)
    
    return masked_data


class AWSClientManager:
    """Manages AWS client instances with proper configuration."""
    
    _clients = {}
    
    @classmethod
    def get_client(cls, service_name: str, **kwargs):
        """Get or create AWS client for service."""
        config = get_aws_config()
        config.update(kwargs)
        
        client_key = f"{service_name}_{hash(str(sorted(config.items())))}"
        
        if client_key not in cls._clients:
            cls._clients[client_key] = boto3.client(service_name, **config)
        
        return cls._clients[client_key]
    
    @classmethod
    def get_resource(cls, service_name: str, **kwargs):
        """Get or create AWS resource for service."""
        config = get_aws_config()
        config.update(kwargs)
        
        return boto3.resource(service_name, **config)


def get_dynamodb_client():
    """Get DynamoDB client."""
    return AWSClientManager.get_client("dynamodb")


def get_dynamodb_resource():
    """Get DynamoDB resource."""
    return AWSClientManager.get_resource("dynamodb")


def get_s3_client():
    """Get S3 client."""
    return AWSClientManager.get_client("s3")


def get_bedrock_client():
    """Get Bedrock Runtime client."""
    return AWSClientManager.get_client("bedrock-runtime")


def get_opensearch_client():
    """Get OpenSearch client."""
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from aws_requests_auth.aws_auth import AWSRequestsAuth
    
    config = get_aws_config()
    
    if "endpoint_url" in config:  # LocalStack
        return OpenSearch(
            hosts=[{"host": "localhost", "port": 4566}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            connection_class=RequestsHttpConnection,
        )
    else:
        # AWS OpenSearch Serverless
        auth = AWSRequestsAuth(
            aws_access_key=config.get("aws_access_key_id"),
            aws_secret_access_key=config.get("aws_secret_access_key"),
            aws_token=config.get("aws_session_token"),
            aws_host=settings.opensearch_endpoint.replace("https://", ""),
            aws_region=settings.aws_region,
            aws_service="aoss",
        )
        
        return OpenSearch(
            hosts=[{"host": settings.opensearch_endpoint.replace("https://", ""), "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )


def handle_aws_error(error: ClientError, operation: str = "AWS operation") -> Dict[str, Any]:
    """Handle AWS client errors and return structured error info."""
    error_code = error.response.get("Error", {}).get("Code", "Unknown")
    error_message = error.response.get("Error", {}).get("Message", str(error))
    
    logger.error(
        "AWS operation failed",
        operation=operation,
        error_code=error_code,
        error_message=error_message,
    )
    
    return {
        "success": False,
        "error_code": error_code,
        "error_message": error_message,
        "operation": operation,
    }


def create_api_response(
    success: bool,
    message: str,
    data: Any = None,
    error_code: Optional[str] = None,
    status_code: int = 200,
) -> Dict[str, Any]:
    """Create standardized API response."""
    response = {
        "success": success,
        "message": message,
        "timestamp": utc_now().isoformat(),
    }
    
    if data is not None:
        response["data"] = data
    
    if error_code:
        response["error_code"] = error_code
    
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(response, default=str),
    }


def parse_lambda_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Lambda event and extract common information."""
    return {
        "http_method": event.get("httpMethod", ""),
        "path": event.get("path", ""),
        "path_parameters": event.get("pathParameters") or {},
        "query_parameters": event.get("queryStringParameters") or {},
        "headers": event.get("headers") or {},
        "body": json.loads(event.get("body", "{}")) if event.get("body") else {},
        "user_id": event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("sub"),
        "tenant_id": event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("custom:tenant_id"),
    }


def validate_tenant_access(user_tenant_id: str, requested_tenant_id: str) -> bool:
    """Validate that user has access to the requested tenant."""
    return user_tenant_id == requested_tenant_id


def get_correlation_id(event: Dict[str, Any]) -> str:
    """Get or generate correlation ID for request tracing."""
    return (
        event.get("headers", {}).get("X-Correlation-ID") or
        event.get("requestContext", {}).get("requestId") or
        generate_id("corr_")
    )