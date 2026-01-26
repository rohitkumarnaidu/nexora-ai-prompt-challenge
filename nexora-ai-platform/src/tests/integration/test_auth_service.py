"""
Integration tests for authentication service.
"""

import pytest
import json
from unittest.mock import patch, Mock

from ...services.auth.handler import lambda_handler, cognito_service, jwt_service


class TestAuthService:
    """Test authentication service integration."""
    
    def test_user_registration_success(self, mock_dynamodb_table):
        """Test successful user registration with Cognito integration."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/register",
            "body": json.dumps({
                "email": "test@example.com",
                "password": "TestPassword123!",
                "first_name": "Test",
                "last_name": "User",
                "tenant_name": "Test Tenant",
                "tenant_type": "INDIVIDUAL",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        with patch("src.shared.utils.get_dynamodb_resource") as mock_dynamodb, \
             patch.object(cognito_service, "register_user") as mock_cognito_register, \
             patch.object(jwt_service, "generate_tokens") as mock_jwt_generate:
            
            mock_table = Mock()
            mock_dynamodb.return_value.Table.return_value = mock_table
            
            # Mock successful Cognito registration
            mock_cognito_register.return_value = {
                "success": True,
                "cognito_sub": "test-cognito-sub-123",
                "user_status": "CONFIRMED"
            }
            
            # Mock JWT token generation
            mock_jwt_generate.return_value = {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 200
            
            body = json.loads(response["body"])
            assert body["success"] is True
            assert "user" in body["data"]
            assert "tokens" in body["data"]
            assert body["data"]["user"]["email"] == "test@example.com"
            
            # Verify Cognito registration was called
            mock_cognito_register.assert_called_once()
            
            # Verify DynamoDB calls
            assert mock_table.put_item.call_count == 2  # User and tenant
    
    def test_user_registration_missing_fields(self):
        """Test user registration with missing fields."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/register",
            "body": json.dumps({
                "email": "test@example.com",
                # Missing password, first_name, and last_name
            }),
            "headers": {},
            "requestContext": {},
        }
        
        response = lambda_handler(event, {})
        
        assert response["statusCode"] == 400
        
        body = json.loads(response["body"])
        assert body["success"] is False
        assert body["error_code"] == "MISSING_FIELDS"
    
    def test_user_registration_invalid_email(self):
        """Test user registration with invalid email."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/register",
            "body": json.dumps({
                "email": "invalid-email",
                "password": "TestPassword123!",
                "first_name": "Test",
                "last_name": "User",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        response = lambda_handler(event, {})
        
        assert response["statusCode"] == 400
        
        body = json.loads(response["body"])
        assert body["success"] is False
        assert body["error_code"] == "INVALID_EMAIL"
    
    def test_user_registration_weak_password(self):
        """Test user registration with weak password."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/register",
            "body": json.dumps({
                "email": "test@example.com",
                "password": "weak",  # Too short
                "first_name": "Test",
                "last_name": "User",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        response = lambda_handler(event, {})
        
        assert response["statusCode"] == 400
        
        body = json.loads(response["body"])
        assert body["success"] is False
        assert body["error_code"] == "WEAK_PASSWORD"
    
    def test_user_registration_cognito_failure(self):
        """Test user registration with Cognito failure."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/register",
            "body": json.dumps({
                "email": "test@example.com",
                "password": "TestPassword123!",
                "first_name": "Test",
                "last_name": "User",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        with patch.object(cognito_service, "register_user") as mock_cognito_register:
            # Mock Cognito registration failure
            mock_cognito_register.return_value = {
                "success": False,
                "error_code": "UsernameExistsException",
                "error_message": "User already exists"
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 400
            
            body = json.loads(response["body"])
            assert body["success"] is False
            assert body["error_code"] == "UsernameExistsException"
    
    def test_user_login_success(self):
        """Test successful user login."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/login",
            "body": json.dumps({
                "email": "test@example.com",
                "password": "TestPassword123!",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        mock_user_data = {
            "user_id": "test-user-123",
            "email": "test@example.com",
            "tenant_id": "test-tenant-123",
            "role": "CREATOR",
            "first_name": "Test",
            "last_name": "User",
        }
        
        with patch("src.shared.utils.get_dynamodb_resource") as mock_dynamodb, \
             patch.object(cognito_service, "authenticate_user") as mock_cognito_auth, \
             patch.object(jwt_service, "generate_tokens") as mock_jwt_generate:
            
            mock_table = Mock()
            mock_table.scan.return_value = {"Items": [mock_user_data]}
            mock_dynamodb.return_value.Table.return_value = mock_table
            
            # Mock successful Cognito authentication
            mock_cognito_auth.return_value = {
                "success": True,
                "access_token": "cognito-access-token",
                "id_token": "cognito-id-token",
                "refresh_token": "cognito-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "cognito_sub": "test-cognito-sub-123",
                "email": "test@example.com",
                "tenant_id": "test-tenant-123"
            }
            
            # Mock JWT token generation
            mock_jwt_generate.return_value = {
                "access_token": "jwt-access-token",
                "refresh_token": "jwt-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 200
            
            body = json.loads(response["body"])
            assert body["success"] is True
            assert body["data"]["user"]["user_id"] == "test-user-123"
            assert body["data"]["user"]["email"] == "test@example.com"
            assert "tokens" in body["data"]
            assert "cognito_tokens" in body["data"]
    
    def test_user_login_missing_credentials(self):
        """Test user login with missing credentials."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/login",
            "body": json.dumps({
                "email": "test@example.com",
                # Missing password
            }),
            "headers": {},
            "requestContext": {},
        }
        
        response = lambda_handler(event, {})
        
        assert response["statusCode"] == 400
        
        body = json.loads(response["body"])
        assert body["success"] is False
        assert body["error_code"] == "MISSING_CREDENTIALS"
    
    def test_user_login_cognito_failure(self):
        """Test user login with Cognito authentication failure."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/login",
            "body": json.dumps({
                "email": "test@example.com",
                "password": "WrongPassword123!",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        with patch.object(cognito_service, "authenticate_user") as mock_cognito_auth:
            # Mock Cognito authentication failure
            mock_cognito_auth.return_value = {
                "success": False,
                "error_code": "NotAuthorizedException",
                "error_message": "Incorrect username or password"
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 401
            
            body = json.loads(response["body"])
            assert body["success"] is False
            assert body["error_code"] == "NotAuthorizedException"
    
    def test_user_login_user_not_found(self):
        """Test user login with user not found in system."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/login",
            "body": json.dumps({
                "email": "test@example.com",
                "password": "TestPassword123!",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        with patch("src.shared.utils.get_dynamodb_resource") as mock_dynamodb, \
             patch.object(cognito_service, "authenticate_user") as mock_cognito_auth:
            
            mock_table = Mock()
            mock_table.scan.return_value = {"Items": []}  # No user found
            mock_dynamodb.return_value.Table.return_value = mock_table
            
            # Mock successful Cognito authentication
            mock_cognito_auth.return_value = {
                "success": True,
                "cognito_sub": "test-cognito-sub-123",
                "email": "test@example.com"
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 404
            
            body = json.loads(response["body"])
            assert body["success"] is False
            assert body["error_code"] == "USER_NOT_FOUND"
    
    def test_token_refresh_jwt_success(self):
        """Test successful JWT token refresh."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/refresh",
            "body": json.dumps({
                "jwt_refresh_token": "valid-jwt-refresh-token",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        with patch.object(jwt_service, "validate_token") as mock_jwt_validate, \
             patch.object(jwt_service, "generate_tokens") as mock_jwt_generate:
            
            # Mock successful token validation
            mock_jwt_validate.return_value = {
                "valid": True,
                "payload": {
                    "sub": "test-user-123",
                    "tenant_id": "test-tenant-123",
                    "role": "CREATOR"
                }
            }
            
            # Mock new token generation
            mock_jwt_generate.return_value = {
                "access_token": "new-jwt-access-token",
                "refresh_token": "new-jwt-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 200
            
            body = json.loads(response["body"])
            assert body["success"] is True
            assert "tokens" in body["data"]
    
    def test_token_refresh_cognito_success(self):
        """Test successful Cognito token refresh."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/refresh",
            "body": json.dumps({
                "refresh_token": "valid-cognito-refresh-token",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        with patch.object(cognito_service, "refresh_token") as mock_cognito_refresh:
            # Mock successful Cognito token refresh
            mock_cognito_refresh.return_value = {
                "success": True,
                "access_token": "new-cognito-access-token",
                "id_token": "new-cognito-id-token",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 200
            
            body = json.loads(response["body"])
            assert body["success"] is True
            assert "cognito_tokens" in body["data"]
    
    def test_token_refresh_missing_token(self):
        """Test token refresh with missing refresh token."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/refresh",
            "body": json.dumps({}),  # No refresh token
            "headers": {},
            "requestContext": {},
        }
        
        response = lambda_handler(event, {})
        
        assert response["statusCode"] == 400
        
        body = json.loads(response["body"])
        assert body["success"] is False
        assert body["error_code"] == "MISSING_REFRESH_TOKEN"
    
    def test_token_validation_jwt_success(self):
        """Test successful JWT token validation."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/validate",
            "body": json.dumps({
                "jwt_token": "valid-jwt-token",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        with patch.object(jwt_service, "validate_token") as mock_jwt_validate:
            # Mock successful token validation
            mock_jwt_validate.return_value = {
                "valid": True,
                "payload": {
                    "sub": "test-user-123",
                    "tenant_id": "test-tenant-123",
                    "role": "CREATOR"
                }
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 200
            
            body = json.loads(response["body"])
            assert body["success"] is True
            assert "payload" in body["data"]
    
    def test_token_validation_cognito_success(self):
        """Test successful Cognito token validation."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/validate",
            "body": json.dumps({
                "access_token": "valid-cognito-access-token",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        with patch.object(cognito_service, "validate_token") as mock_cognito_validate:
            # Mock successful Cognito token validation
            mock_cognito_validate.return_value = {
                "success": True,
                "cognito_sub": "test-cognito-sub-123",
                "email": "test@example.com",
                "tenant_id": "test-tenant-123"
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 200
            
            body = json.loads(response["body"])
            assert body["success"] is True
            assert "user_info" in body["data"]
    
    def test_token_validation_invalid_token(self):
        """Test token validation with invalid token."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/validate",
            "body": json.dumps({
                "jwt_token": "invalid-jwt-token",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        with patch.object(jwt_service, "validate_token") as mock_jwt_validate:
            # Mock invalid token validation
            mock_jwt_validate.return_value = {
                "valid": False,
                "error": "Token has expired"
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 401
            
            body = json.loads(response["body"])
            assert body["success"] is False
            assert body["error_code"] == "INVALID_TOKEN"
    
    def test_google_auth_initiation(self):
        """Test Google OAuth initiation."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/google",
            "body": json.dumps({
                "redirect_uri": "http://localhost:3000/auth/callback",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        with patch.object(cognito_service, "initiate_google_auth") as mock_google_auth:
            # Mock Google auth URL generation
            mock_google_auth.return_value = "https://cognito-domain.auth.region.amazoncognito.com/oauth2/authorize?..."
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 200
            
            body = json.loads(response["body"])
            assert body["success"] is True
            assert "auth_url" in body["data"]
    
    def test_google_callback_existing_user(self):
        """Test Google OAuth callback for existing user."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/google/callback",
            "body": json.dumps({
                "code": "oauth-authorization-code",
                "redirect_uri": "http://localhost:3000/auth/callback",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        mock_user_data = {
            "user_id": "test-user-123",
            "email": "test@example.com",
            "tenant_id": "test-tenant-123",
            "role": "CREATOR",
            "first_name": "Test",
            "last_name": "User",
        }
        
        with patch("src.shared.utils.get_dynamodb_resource") as mock_dynamodb, \
             patch.object(cognito_service, "handle_oauth_callback") as mock_oauth_callback, \
             patch.object(jwt_service, "generate_tokens") as mock_jwt_generate:
            
            mock_table = Mock()
            mock_table.scan.return_value = {"Items": [mock_user_data]}
            mock_dynamodb.return_value.Table.return_value = mock_table
            
            # Mock successful OAuth callback
            mock_oauth_callback.return_value = {
                "success": True,
                "access_token": "cognito-access-token",
                "id_token": "cognito-id-token",
                "refresh_token": "cognito-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "cognito_sub": "test-cognito-sub-123",
                "email": "test@example.com"
            }
            
            # Mock JWT token generation
            mock_jwt_generate.return_value = {
                "access_token": "jwt-access-token",
                "refresh_token": "jwt-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 200
            
            body = json.loads(response["body"])
            assert body["success"] is True
            assert body["message"] == "Google login successful"
            assert "user" in body["data"]
            assert "tokens" in body["data"]
    
    def test_google_callback_new_user(self):
        """Test Google OAuth callback for new user."""
        event = {
            "httpMethod": "POST",
            "path": "/auth/google/callback",
            "body": json.dumps({
                "code": "oauth-authorization-code",
                "redirect_uri": "http://localhost:3000/auth/callback",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        with patch("src.shared.utils.get_dynamodb_resource") as mock_dynamodb, \
             patch.object(cognito_service, "handle_oauth_callback") as mock_oauth_callback:
            
            mock_table = Mock()
            mock_table.scan.return_value = {"Items": []}  # No existing user
            mock_dynamodb.return_value.Table.return_value = mock_table
            
            # Mock successful OAuth callback
            mock_oauth_callback.return_value = {
                "success": True,
                "access_token": "cognito-access-token",
                "id_token": "cognito-id-token",
                "refresh_token": "cognito-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "cognito_sub": "test-cognito-sub-123",
                "email": "newuser@example.com"
            }
            
            response = lambda_handler(event, {})
            
            assert response["statusCode"] == 200
            
            body = json.loads(response["body"])
            assert body["success"] is True
            assert body["message"] == "New Google user - registration required"
            assert body["data"]["new_user"] is True
            assert body["data"]["email"] == "newuser@example.com"
    
    def test_invalid_request(self):
        """Test invalid request handling."""
        event = {
            "httpMethod": "GET",  # Invalid method
            "path": "/auth/invalid",
            "body": json.dumps({}),
            "headers": {},
            "requestContext": {},
        }
        
        response = lambda_handler(event, {})
        
        assert response["statusCode"] == 400
        
        body = json.loads(response["body"])
        assert body["success"] is False
        assert body["error_code"] == "INVALID_REQUEST"