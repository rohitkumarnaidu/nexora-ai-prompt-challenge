"""
Unit tests for authentication services (Cognito and JWT).
"""

import pytest
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from botocore.exceptions import ClientError

from ...services.auth.handler import CognitoAuthService, JWTTokenService
from ...shared.config import settings


class TestCognitoAuthService:
    """Test Cognito authentication service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cognito_service = CognitoAuthService()
    
    def test_register_user_success(self):
        """Test successful user registration in Cognito."""
        with patch.object(self.cognito_service, 'cognito_client') as mock_client:
            # Mock successful user creation
            mock_client.admin_create_user.return_value = {
                "User": {
                    "Username": "test-cognito-sub-123",
                    "UserStatus": "CONFIRMED"
                }
            }
            
            result = self.cognito_service.register_user(
                email="test@example.com",
                password="TestPassword123!",
                first_name="Test",
                last_name="User",
                tenant_id="test-tenant-123"
            )
            
            assert result["success"] is True
            assert result["cognito_sub"] == "test-cognito-sub-123"
            assert result["user_status"] == "CONFIRMED"
            
            # Verify Cognito calls
            mock_client.admin_create_user.assert_called_once()
            mock_client.admin_set_user_password.assert_called_once()
    
    def test_register_user_failure(self):
        """Test user registration failure in Cognito."""
        with patch.object(self.cognito_service, 'cognito_client') as mock_client:
            # Mock Cognito error
            mock_client.admin_create_user.side_effect = ClientError(
                error_response={
                    "Error": {
                        "Code": "UsernameExistsException",
                        "Message": "User already exists"
                    }
                },
                operation_name="AdminCreateUser"
            )
            
            result = self.cognito_service.register_user(
                email="test@example.com",
                password="TestPassword123!",
                first_name="Test",
                last_name="User",
                tenant_id="test-tenant-123"
            )
            
            assert result["success"] is False
            assert result["error_code"] == "UsernameExistsException"
            assert result["error_message"] == "User already exists"
    
    def test_authenticate_user_success(self):
        """Test successful user authentication."""
        with patch.object(self.cognito_service, 'cognito_client') as mock_client:
            # Mock successful authentication
            mock_client.admin_initiate_auth.return_value = {
                "AuthenticationResult": {
                    "AccessToken": "test-access-token",
                    "IdToken": "MOCK_ID_TOKEN",
                    "RefreshToken": "test-refresh-token",
                    "ExpiresIn": 3600,
                    "TokenType": "Bearer"
                }
            }
            
            result = self.cognito_service.authenticate_user(
                email="test@example.com",
                password="TestPassword123!"
            )
            
            assert result["success"] is True
            assert result["access_token"] == "test-access-token"
            assert result["expires_in"] == 3600
            assert "cognito_sub" in result
            assert "email" in result
    
    def test_authenticate_user_failure(self):
        """Test user authentication failure."""
        with patch.object(self.cognito_service, 'cognito_client') as mock_client:
            # Mock authentication error
            mock_client.admin_initiate_auth.side_effect = ClientError(
                error_response={
                    "Error": {
                        "Code": "NotAuthorizedException",
                        "Message": "Incorrect username or password"
                    }
                },
                operation_name="AdminInitiateAuth"
            )
            
            result = self.cognito_service.authenticate_user(
                email="test@example.com",
                password="WrongPassword123!"
            )
            
            assert result["success"] is False
            assert result["error_code"] == "NotAuthorizedException"
            assert result["error_message"] == "Incorrect username or password"
    
    def test_authenticate_user_challenge_required(self):
        """Test authentication with challenge required."""
        with patch.object(self.cognito_service, 'cognito_client') as mock_client:
            # Mock challenge response
            mock_client.admin_initiate_auth.return_value = {
                "ChallengeName": "NEW_PASSWORD_REQUIRED",
                "Session": "test-session-token"
            }
            
            result = self.cognito_service.authenticate_user(
                email="test@example.com",
                password="TempPassword123!"
            )
            
            assert result["success"] is False
            assert result["error_code"] == "CHALLENGE_REQUIRED"
            assert result["challenge_name"] == "NEW_PASSWORD_REQUIRED"
            assert result["session"] == "test-session-token"
    
    def test_refresh_token_success(self):
        """Test successful token refresh."""
        with patch.object(self.cognito_service, 'cognito_client') as mock_client:
            # Mock successful token refresh
            mock_client.admin_initiate_auth.return_value = {
                "AuthenticationResult": {
                    "AccessToken": "new-access-token",
                    "IdToken": "new-id-token",
                    "ExpiresIn": 3600,
                    "TokenType": "Bearer"
                }
            }
            
            result = self.cognito_service.refresh_token("test-refresh-token")
            
            assert result["success"] is True
            assert result["access_token"] == "new-access-token"
            assert result["id_token"] == "new-id-token"
            assert result["expires_in"] == 3600
    
    def test_refresh_token_failure(self):
        """Test token refresh failure."""
        with patch.object(self.cognito_service, 'cognito_client') as mock_client:
            # Mock refresh error
            mock_client.admin_initiate_auth.side_effect = ClientError(
                error_response={
                    "Error": {
                        "Code": "NotAuthorizedException",
                        "Message": "Refresh Token has expired"
                    }
                },
                operation_name="AdminInitiateAuth"
            )
            
            result = self.cognito_service.refresh_token("expired-refresh-token")
            
            assert result["success"] is False
            assert result["error_code"] == "NotAuthorizedException"
            assert result["error_message"] == "Refresh Token has expired"
    
    def test_validate_token_success(self):
        """Test successful token validation."""
        with patch.object(self.cognito_service, 'cognito_client') as mock_client:
            # Mock successful token validation
            mock_client.get_user.return_value = {
                "Username": "test-username",
                "UserAttributes": [
                    {"Name": "sub", "Value": "test-cognito-sub-123"},
                    {"Name": "email", "Value": "test@example.com"},
                    {"Name": "custom:tenant_id", "Value": "test-tenant-123"}
                ]
            }
            
            result = self.cognito_service.validate_token("valid-access-token")
            
            assert result["success"] is True
            assert result["username"] == "test-username"
            assert result["cognito_sub"] == "test-cognito-sub-123"
            assert result["email"] == "test@example.com"
            assert result["tenant_id"] == "test-tenant-123"
    
    def test_validate_token_failure(self):
        """Test token validation failure."""
        with patch.object(self.cognito_service, 'cognito_client') as mock_client:
            # Mock validation error
            mock_client.get_user.side_effect = ClientError(
                error_response={
                    "Error": {
                        "Code": "NotAuthorizedException",
                        "Message": "Access Token has expired"
                    }
                },
                operation_name="GetUser"
            )
            
            result = self.cognito_service.validate_token("expired-access-token")
            
            assert result["success"] is False
            assert result["error_code"] == "NotAuthorizedException"
            assert result["error_message"] == "Access Token has expired"
    
    def test_initiate_google_auth(self):
        """Test Google OAuth URL generation."""
        redirect_uri = "http://localhost:3000/auth/callback"
        
        with patch.object(settings, 'stage', 'dev'), \
             patch.object(settings, 'aws_region', 'us-east-1'):
            
            auth_url = self.cognito_service.initiate_google_auth(redirect_uri)
            
            assert "nexora-auth-dev.auth.us-east-1.amazoncognito.com" in auth_url
            assert "response_type=code" in auth_url
            assert "identity_provider=Google" in auth_url
            assert redirect_uri in auth_url
    
    def test_handle_oauth_callback_success(self):
        """Test successful OAuth callback handling."""
        with patch('requests.post') as mock_post:
            # Mock successful token exchange
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "oauth-access-token",
                "id_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0LXN1YiIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9.fake-signature",
                "refresh_token": "oauth-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
            mock_post.return_value = mock_response
            
            result = self.cognito_service.handle_oauth_callback(
                authorization_code="test-auth-code",
                redirect_uri="http://localhost:3000/auth/callback"
            )
            
            assert result["success"] is True
            assert result["access_token"] == "oauth-access-token"
            assert "cognito_sub" in result
            assert "email" in result
    
    def test_handle_oauth_callback_failure(self):
        """Test OAuth callback handling failure."""
        with patch('requests.post') as mock_post:
            # Mock failed token exchange
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Invalid authorization code"
            mock_post.return_value = mock_response
            
            result = self.cognito_service.handle_oauth_callback(
                authorization_code="invalid-auth-code",
                redirect_uri="http://localhost:3000/auth/callback"
            )
            
            assert result["success"] is False
            assert result["error_code"] == "OAUTH_EXCHANGE_FAILED"


class TestJWTTokenService:
    """Test JWT token service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.jwt_service = JWTTokenService()
        self.jwt_service.secret_key = "test-secret-key"
    
    def test_generate_tokens(self):
        """Test JWT token generation."""
        tokens = self.jwt_service.generate_tokens(
            user_id="test-user-123",
            tenant_id="test-tenant-123",
            role="CREATOR"
        )
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["expires_in"] == 3600  # 60 minutes
        assert tokens["token_type"] == "Bearer"
        
        # Verify token contents
        access_payload = jwt.decode(
            tokens["access_token"], 
            self.jwt_service.secret_key, 
            algorithms=[self.jwt_service.algorithm]
        )
        
        assert access_payload["sub"] == "test-user-123"
        assert access_payload["tenant_id"] == "test-tenant-123"
        assert access_payload["role"] == "CREATOR"
        assert access_payload["type"] == "access"
        
        refresh_payload = jwt.decode(
            tokens["refresh_token"], 
            self.jwt_service.secret_key, 
            algorithms=[self.jwt_service.algorithm]
        )
        
        assert refresh_payload["sub"] == "test-user-123"
        assert refresh_payload["tenant_id"] == "test-tenant-123"
        assert refresh_payload["type"] == "refresh"
    
    def test_validate_token_success(self):
        """Test successful token validation."""
        # Generate a valid token
        tokens = self.jwt_service.generate_tokens(
            user_id="test-user-123",
            tenant_id="test-tenant-123",
            role="CREATOR"
        )
        
        # Validate access token
        result = self.jwt_service.validate_token(tokens["access_token"], "access")
        
        assert result["valid"] is True
        assert result["payload"]["sub"] == "test-user-123"
        assert result["payload"]["tenant_id"] == "test-tenant-123"
        assert result["payload"]["role"] == "CREATOR"
        assert result["payload"]["type"] == "access"
        
        # Validate refresh token
        result = self.jwt_service.validate_token(tokens["refresh_token"], "refresh")
        
        assert result["valid"] is True
        assert result["payload"]["sub"] == "test-user-123"
        assert result["payload"]["tenant_id"] == "test-tenant-123"
        assert result["payload"]["type"] == "refresh"
    
    def test_validate_token_wrong_type(self):
        """Test token validation with wrong token type."""
        # Generate tokens
        tokens = self.jwt_service.generate_tokens(
            user_id="test-user-123",
            tenant_id="test-tenant-123",
            role="CREATOR"
        )
        
        # Try to validate access token as refresh token
        result = self.jwt_service.validate_token(tokens["access_token"], "refresh")
        
        assert result["valid"] is False
        assert "Invalid token type" in result["error"]
    
    def test_validate_token_expired(self):
        """Test validation of expired token."""
        # Create an expired token
        now = datetime.utcnow()
        expired_payload = {
            "sub": "test-user-123",
            "tenant_id": "test-tenant-123",
            "role": "CREATOR",
            "type": "access",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1)  # Expired 1 hour ago
        }
        
        expired_token = jwt.encode(
            expired_payload, 
            self.jwt_service.secret_key, 
            algorithm=self.jwt_service.algorithm
        )
        
        result = self.jwt_service.validate_token(expired_token, "access")
        
        assert result["valid"] is False
        assert "Token has expired" in result["error"]
    
    def test_validate_token_invalid(self):
        """Test validation of invalid token."""
        result = self.jwt_service.validate_token("invalid.jwt.token", "access")
        
        assert result["valid"] is False
        assert "Invalid token" in result["error"]
    
    def test_validate_token_wrong_signature(self):
        """Test validation of token with wrong signature."""
        # Create token with different secret
        wrong_secret_payload = {
            "sub": "test-user-123",
            "tenant_id": "test-tenant-123",
            "role": "CREATOR",
            "type": "access",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        
        wrong_token = jwt.encode(
            wrong_secret_payload, 
            "wrong-secret-key",  # Different secret
            algorithm=self.jwt_service.algorithm
        )
        
        result = self.jwt_service.validate_token(wrong_token, "access")
        
        assert result["valid"] is False
        assert "Invalid token" in result["error"]
    
    def test_token_expiration_times(self):
        """Test that tokens have correct expiration times."""
        tokens = self.jwt_service.generate_tokens(
            user_id="test-user-123",
            tenant_id="test-tenant-123",
            role="CREATOR"
        )
        
        # Decode tokens to check expiration
        access_payload = jwt.decode(
            tokens["access_token"], 
            self.jwt_service.secret_key, 
            algorithms=[self.jwt_service.algorithm]
        )
        
        refresh_payload = jwt.decode(
            tokens["refresh_token"], 
            self.jwt_service.secret_key, 
            algorithms=[self.jwt_service.algorithm]
        )
        
        # Check that access token expires in ~60 minutes
        access_exp = datetime.fromtimestamp(access_payload["exp"])
        access_iat = datetime.fromtimestamp(access_payload["iat"])
        access_duration = access_exp - access_iat
        
        assert abs(access_duration.total_seconds() - 3600) < 60  # Within 1 minute of 1 hour
        
        # Check that refresh token expires in ~30 days
        refresh_exp = datetime.fromtimestamp(refresh_payload["exp"])
        refresh_iat = datetime.fromtimestamp(refresh_payload["iat"])
        refresh_duration = refresh_exp - refresh_iat
        
        expected_refresh_seconds = 30 * 24 * 60 * 60  # 30 days
        assert abs(refresh_duration.total_seconds() - expected_refresh_seconds) < 3600  # Within 1 hour of 30 days