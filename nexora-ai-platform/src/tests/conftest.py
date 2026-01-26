"""
Pytest configuration and fixtures for Nexora AI Platform tests.
"""

import os
import pytest
import boto3
from moto import mock_dynamodb, mock_s3, mock_cognitoidp
from unittest.mock import Mock, patch

# Set test environment
os.environ["STAGE"] = "test"
os.environ["USE_LOCALSTACK"] = "true"
os.environ["LOCALSTACK_ENDPOINT"] = "http://localhost:4566"


@pytest.fixture(scope="session")
def aws_credentials():
    """Mock AWS credentials for testing."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB table for testing."""
    with mock_dynamodb():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        
        # Create test table
        table = dynamodb.create_table(
            TableName="test-table",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        
        yield table


@pytest.fixture
def mock_s3_bucket():
    """Mock S3 bucket for testing."""
    with mock_s3():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket"
        s3.create_bucket(Bucket=bucket_name)
        yield bucket_name


@pytest.fixture
def mock_cognito():
    """Mock Cognito User Pool for testing."""
    with mock_cognitoidp():
        client = boto3.client("cognito-idp", region_name="us-east-1")
        
        # Create user pool
        user_pool = client.create_user_pool(
            PoolName="test-pool",
            Policies={
                "PasswordPolicy": {
                    "MinimumLength": 8,
                    "RequireUppercase": True,
                    "RequireLowercase": True,
                    "RequireNumbers": True,
                    "RequireSymbols": True,
                }
            },
        )
        
        # Create user pool client
        client.create_user_pool_client(
            UserPoolId=user_pool["UserPool"]["Id"],
            ClientName="test-client",
        )
        
        yield user_pool["UserPool"]["Id"]


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "user_id": "test-user-123",
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "tenant_id": "test-tenant-123",
        "role": "CREATOR",
    }


@pytest.fixture
def sample_tenant_data():
    """Sample tenant data for testing."""
    return {
        "tenant_id": "test-tenant-123",
        "name": "Test Tenant",
        "type": "INDIVIDUAL",
        "subscription_tier": "FREE",
    }


@pytest.fixture
def sample_content_request():
    """Sample content request for testing."""
    return {
        "request_id": "test-request-123",
        "tenant_id": "test-tenant-123",
        "user_id": "test-user-123",
        "content_type": "BLOG_POST",
        "prompt": "Write a blog post about AI",
        "automation_mode": "PARTIAL",
    }


@pytest.fixture
def mock_bedrock_client():
    """Mock Bedrock client for testing."""
    with patch("boto3.client") as mock_client:
        mock_bedrock = Mock()
        mock_client.return_value = mock_bedrock
        
        # Mock invoke_model response
        mock_bedrock.invoke_model.return_value = {
            "body": Mock(read=lambda: b'{"completion": "Test generated content"}'),
            "contentType": "application/json",
        }
        
        yield mock_bedrock


@pytest.fixture
def mock_opensearch_client():
    """Mock OpenSearch client for testing."""
    with patch("src.shared.utils.get_opensearch_client") as mock_client:
        mock_os = Mock()
        mock_client.return_value = mock_os
        
        # Mock search response
        mock_os.search.return_value = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_source": {
                            "content": "Test document content",
                            "title": "Test Document",
                        }
                    }
                ],
            }
        }
        
        yield mock_os