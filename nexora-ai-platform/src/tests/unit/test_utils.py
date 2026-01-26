"""
Unit tests for shared utilities.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from ...shared.utils import (
    generate_id,
    generate_short_id,
    utc_now,
    to_iso_string,
    from_iso_string,
    hash_string,
    truncate_text,
    sanitize_filename,
    calculate_reading_time,
    extract_keywords,
    chunk_text,
    validate_email,
    mask_sensitive_data,
    create_api_response,
    parse_lambda_event,
)


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_generate_id(self):
        """Test ID generation."""
        # Test without prefix
        id1 = generate_id()
        assert isinstance(id1, str)
        assert len(id1) == 36  # UUID length
        
        # Test with prefix
        id2 = generate_id("user_")
        assert id2.startswith("user_")
        assert len(id2) == 41  # prefix + UUID
        
        # Test uniqueness
        assert id1 != id2
    
    def test_generate_short_id(self):
        """Test short ID generation."""
        short_id = generate_short_id(8)
        assert isinstance(short_id, str)
        assert len(short_id) == 8
        
        # Test different lengths
        short_id_12 = generate_short_id(12)
        assert len(short_id_12) == 12
    
    def test_utc_now(self):
        """Test UTC datetime generation."""
        now = utc_now()
        assert isinstance(now, datetime)
        assert now.tzinfo == timezone.utc
    
    def test_iso_string_conversion(self):
        """Test ISO string conversion."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        iso_string = to_iso_string(dt)
        
        assert isinstance(iso_string, str)
        assert "2024-01-15T10:30:00" in iso_string
        
        # Test round-trip conversion
        converted_dt = from_iso_string(iso_string)
        assert converted_dt.year == 2024
        assert converted_dt.month == 1
        assert converted_dt.day == 15
    
    def test_hash_string(self):
        """Test string hashing."""
        text = "test string"
        hash1 = hash_string(text)
        hash2 = hash_string(text)
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 hex length
        assert hash1 == hash2  # Same input, same hash
        
        # Different input, different hash
        hash3 = hash_string("different string")
        assert hash1 != hash3
    
    def test_truncate_text(self):
        """Test text truncation."""
        text = "This is a long text that needs to be truncated"
        
        # Test normal truncation
        truncated = truncate_text(text, 20)
        assert len(truncated) == 20
        assert truncated.endswith("...")
        
        # Test text shorter than max length
        short_text = "Short"
        truncated_short = truncate_text(short_text, 20)
        assert truncated_short == "Short"
        
        # Test custom suffix
        truncated_custom = truncate_text(text, 20, " [more]")
        assert truncated_custom.endswith(" [more]")
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        unsafe_filename = "file<name>with:unsafe/chars*.txt"
        safe_filename = sanitize_filename(unsafe_filename)
        
        assert "<" not in safe_filename
        assert ">" not in safe_filename
        assert ":" not in safe_filename
        assert "/" not in safe_filename
        assert "*" not in safe_filename
        assert safe_filename == "file_name_with_unsafe_chars_.txt"
    
    def test_calculate_reading_time(self):
        """Test reading time calculation."""
        # Test with 200 words (default WPM)
        text = " ".join(["word"] * 200)
        reading_time = calculate_reading_time(text)
        assert reading_time == 1  # 200 words / 200 WPM = 1 minute
        
        # Test with custom WPM
        reading_time_fast = calculate_reading_time(text, words_per_minute=400)
        assert reading_time_fast == 1  # Minimum 1 minute
        
        # Test with more words
        long_text = " ".join(["word"] * 600)
        reading_time_long = calculate_reading_time(long_text)
        assert reading_time_long == 3  # 600 words / 200 WPM = 3 minutes
    
    def test_extract_keywords(self):
        """Test keyword extraction."""
        text = "artificial intelligence machine learning deep learning neural networks"
        keywords = extract_keywords(text, max_keywords=3)
        
        assert isinstance(keywords, list)
        assert len(keywords) <= 3
        assert "learning" in keywords  # Should appear twice
    
    def test_chunk_text(self):
        """Test text chunking."""
        text = "This is a test. " * 100  # Create long text
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 1
        assert all(len(chunk) <= 120 for chunk in chunks)  # chunk_size + some buffer
    
    def test_validate_email(self):
        """Test email validation."""
        # Valid emails
        assert validate_email("test@example.com") is True
        assert validate_email("user.name+tag@domain.co.uk") is True
        
        # Invalid emails
        assert validate_email("invalid-email") is False
        assert validate_email("@domain.com") is False
        assert validate_email("user@") is False
    
    def test_mask_sensitive_data(self):
        """Test sensitive data masking."""
        data = {
            "username": "testuser",
            "password": "secretpassword",
            "api_key": "sk-1234567890abcdef",
            "normal_field": "normal_value",
        }
        
        masked = mask_sensitive_data(data)
        
        assert masked["username"] == "testuser"  # Not sensitive
        assert masked["password"] == "se***rd"  # Masked
        assert masked["api_key"] == "sk***ef"  # Masked
        assert masked["normal_field"] == "normal_value"  # Not sensitive


class TestAPIHelpers:
    """Test API helper functions."""
    
    def test_create_api_response_success(self):
        """Test successful API response creation."""
        response = create_api_response(
            success=True,
            message="Operation successful",
            data={"result": "test"},
        )
        
        assert response["statusCode"] == 200
        assert "application/json" in response["headers"]["Content-Type"]
        
        import json
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["message"] == "Operation successful"
        assert body["data"]["result"] == "test"
    
    def test_create_api_response_error(self):
        """Test error API response creation."""
        response = create_api_response(
            success=False,
            message="Operation failed",
            error_code="VALIDATION_ERROR",
            status_code=400,
        )
        
        assert response["statusCode"] == 400
        
        import json
        body = json.loads(response["body"])
        assert body["success"] is False
        assert body["error_code"] == "VALIDATION_ERROR"
    
    def test_parse_lambda_event(self):
        """Test Lambda event parsing."""
        event = {
            "httpMethod": "POST",
            "path": "/api/v1/content",
            "pathParameters": {"id": "123"},
            "queryStringParameters": {"filter": "active"},
            "headers": {"Authorization": "Bearer token"},
            "body": '{"title": "Test Content"}',
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "sub": "user-123",
                        "custom:tenant_id": "tenant-456",
                    }
                }
            },
        }
        
        parsed = parse_lambda_event(event)
        
        assert parsed["http_method"] == "POST"
        assert parsed["path"] == "/api/v1/content"
        assert parsed["path_parameters"]["id"] == "123"
        assert parsed["query_parameters"]["filter"] == "active"
        assert parsed["body"]["title"] == "Test Content"
        assert parsed["user_id"] == "user-123"
        assert parsed["tenant_id"] == "tenant-456"
    
    def test_parse_lambda_event_minimal(self):
        """Test Lambda event parsing with minimal data."""
        event = {}
        parsed = parse_lambda_event(event)
        
        assert parsed["http_method"] == ""
        assert parsed["path"] == ""
        assert parsed["path_parameters"] == {}
        assert parsed["query_parameters"] == {}
        assert parsed["headers"] == {}
        assert parsed["body"] == {}
        assert parsed["user_id"] is None
        assert parsed["tenant_id"] is None