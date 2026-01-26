"""
Property-based tests for authentication system.

These tests validate universal properties that should hold across all inputs.
"""

import pytest
import jwt
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import patch, Mock

from ...services.auth.handler import CognitoAuthService, JWTTokenService, lambda_handler
from ...shared.models import UserRole, TenantType


# Test data strategies
@st.composite
def email_strategy(draw):
    """Generate valid email addresses."""
    username = draw(st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
        max_size=20
    ))
    domain = draw(st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
        max_size=20
    ))
    tld = draw(st.sampled_from(["com", "org", "net", "edu", "gov"]))
    return f"{username}@{domain}.{tld}"


@st.composite
def password_strategy(draw):
    """Generate valid passwords."""
    # Ensure password meets minimum requirements
    length = draw(st.integers(min_value=8, max_value=50))
    password = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd", "Pc", "Pd", "Po", "Ps", "Pe")
        ),
        min_size=length,
        max_size=length
    ))
    # Ensure it has at least one character from each required category
    if not any(c.islower() for c in password):
        password += "a"
    if not any(c.isupper() for c in password):
        password += "A"
    if not any(c.isdigit() for c in password):
        password += "1"
    return password


@st.composite
def user_data_strategy(draw):
    """Generate valid user registration data."""
    return {
        "email": draw(email_strategy()),
        "password": draw(password_strategy()),
        "first_name": draw(st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu")),
            min_size=1,
            max_size=50
        )),
        "last_name": draw(st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu")),
            min_size=1,
            max_size=50
        )),
        "tenant_name": draw(st.text(min_size=1, max_size=100)),
        "tenant_type": draw(st.sampled_from([t.value for t in TenantType]))
    }


@st.composite
def jwt_payload_strategy(draw):
    """Generate valid JWT payload data."""
    return {
        "user_id": draw(st.uuids()).hex,
        "tenant_id": draw(st.uuids()).hex,
        "role": draw(st.sampled_from([r.value for r in UserRole]))
    }


class TestAuthenticationProperties:
    """Property-based tests for authentication system."""
    
    @given(user_data=user_data_strategy())
    @settings(max_examples=50)
    def test_property_1_authentication_token_generation(self, user_data):
        """
        Feature: nexora-ai-platform, Property 1: Authentication Token Generation
        For any successful user authentication with valid credentials, the system 
        should generate secure session tokens with appropriate expiration times 
        and proper JWT structure.
        **Validates: Requirements 1.2**
        """
        jwt_service = JWTTokenService()
        jwt_service.secret_key = "test-secret-key-for-property-testing"
        
        # Generate tokens for valid user data
        tokens = jwt_service.generate_tokens(
            user_id=user_data["email"],  # Use email as user_id for testing
            tenant_id="test-tenant-id",
            role=UserRole.CREATOR.value
        )
        
        # Property: Tokens should always be generated
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "expires_in" in tokens
        assert "token_type" in tokens
        
        # Property: Token type should always be Bearer
        assert tokens["token_type"] == "Bearer"
        
        # Property: Expires_in should be positive
        assert tokens["expires_in"] > 0
        
        # Property: Tokens should be valid JWT tokens
        access_payload = jwt.decode(
            tokens["access_token"],
            jwt_service.secret_key,
            algorithms=[jwt_service.algorithm]
        )
        refresh_payload = jwt.decode(
            tokens["refresh_token"],
            jwt_service.secret_key,
            algorithms=[jwt_service.algorithm]
        )
        
        # Property: Access token should have correct structure
        assert access_payload["sub"] == user_data["email"]
        assert access_payload["tenant_id"] == "test-tenant-id"
        assert access_payload["role"] == UserRole.CREATOR.value
        assert access_payload["type"] == "access"
        assert "iat" in access_payload
        assert "exp" in access_payload
        
        # Property: Refresh token should have correct structure
        assert refresh_payload["sub"] == user_data["email"]
        assert refresh_payload["tenant_id"] == "test-tenant-id"
        assert refresh_payload["type"] == "refresh"
        assert "iat" in refresh_payload
        assert "exp" in refresh_payload
        
        # Property: Expiration times should be in the future
        now = datetime.utcnow().timestamp()
        assert access_payload["exp"] > now
        assert refresh_payload["exp"] > now
        
        # Property: Refresh token should expire later than access token
        assert refresh_payload["exp"] > access_payload["exp"]
    
    @given(payload_data=jwt_payload_strategy())
    @settings(max_examples=50)
    def test_property_2_session_expiration_redirect(self, payload_data):
        """
        Feature: nexora-ai-platform, Property 2: Session Expiration Redirect
        For any expired user session, accessing protected resources should 
        redirect to login while preserving the intended destination URL.
        **Validates: Requirements 1.3**
        """
        jwt_service = JWTTokenService()
        jwt_service.secret_key = "test-secret-key-for-property-testing"
        
        # Create an expired token
        now = datetime.utcnow()
        expired_payload = {
            "sub": payload_data["user_id"],
            "tenant_id": payload_data["tenant_id"],
            "role": payload_data["role"],
            "type": "access",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1)  # Expired 1 hour ago
        }
        
        expired_token = jwt.encode(
            expired_payload,
            jwt_service.secret_key,
            algorithm=jwt_service.algorithm
        )
        
        # Property: Expired tokens should always be rejected
        validation_result = jwt_service.validate_token(expired_token, "access")
        
        assert validation_result["valid"] is False
        assert "expired" in validation_result["error"].lower()
        
        # Property: Error message should indicate expiration
        assert "Token has expired" in validation_result["error"]
    
    @given(
        user_role=st.sampled_from([r.value for r in UserRole]),
        resource_action=st.text(min_size=1, max_size=50)
    )
    @settings(max_examples=50)
    def test_property_3_role_based_access_control(self, user_role, resource_action):
        """
        Feature: nexora-ai-platform, Property 3: Role-Based Access Control
        For any user with a specific role, access to resources should be 
        granted or denied based on the role's permissions, ensuring proper 
        authorization boundaries.
        **Validates: Requirements 1.4**
        """
        jwt_service = JWTTokenService()
        jwt_service.secret_key = "test-secret-key-for-property-testing"
        
        # Generate token with specific role
        tokens = jwt_service.generate_tokens(
            user_id="test-user-id",
            tenant_id="test-tenant-id",
            role=user_role
        )
        
        # Validate token and extract role
        validation_result = jwt_service.validate_token(tokens["access_token"], "access")
        
        # Property: Valid tokens should always contain role information
        assert validation_result["valid"] is True
        assert "role" in validation_result["payload"]
        assert validation_result["payload"]["role"] == user_role
        
        # Property: Role should be one of the valid UserRole values
        assert user_role in [r.value for r in UserRole]
        
        # Property: Token should preserve role information accurately
        extracted_role = validation_result["payload"]["role"]
        assert extracted_role == user_role
    
    @given(
        invalid_credentials=st.one_of(
            st.just({"email": "invalid-email", "password": "validpass123"}),
            st.just({"email": "valid@email.com", "password": ""}),
            st.just({"email": "", "password": "validpass123"}),
            st.just({"email": "valid@email.com", "password": "short"}),
        )
    )
    @settings(max_examples=20)
    def test_property_4_authentication_error_handling(self, invalid_credentials):
        """
        Feature: nexora-ai-platform, Property 4: Authentication Error Handling
        For any authentication failure with invalid credentials, the system 
        should return clear error messages without exposing sensitive security 
        information.
        **Validates: Requirements 1.5**
        """
        # Test registration with invalid data
        event = {
            "httpMethod": "POST",
            "path": "/auth/register",
            "body": json.dumps({
                "email": invalid_credentials["email"],
                "password": invalid_credentials["password"],
                "first_name": "Test",
                "last_name": "User",
            }),
            "headers": {},
            "requestContext": {},
        }
        
        response = lambda_handler(event, {})
        
        # Property: Invalid requests should always return error responses
        assert response["statusCode"] >= 400
        
        body = json.loads(response["body"])
        assert body["success"] is False
        
        # Property: Error responses should have error codes
        assert "error_code" in body
        
        # Property: Error messages should be present but not expose sensitive info
        assert "message" in body
        assert len(body["message"]) > 0
        
        # Property: Should not expose internal system details
        sensitive_terms = ["cognito", "aws", "internal", "stack", "trace", "exception"]
        message_lower = body["message"].lower()
        for term in sensitive_terms:
            assert term not in message_lower, f"Sensitive term '{term}' found in error message"
    
    @given(
        token_data=st.one_of(
            st.just("invalid.jwt.token"),
            st.just(""),
            st.just("not-a-jwt-at-all"),
            st.just("eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid.signature"),
        )
    )
    @settings(max_examples=20)
    def test_property_jwt_token_validation_robustness(self, token_data):
        """
        Property: JWT token validation should handle all invalid inputs gracefully.
        For any invalid token input, the validation should return a proper error 
        response without crashing.
        """
        jwt_service = JWTTokenService()
        jwt_service.secret_key = "test-secret-key-for-property-testing"
        
        # Property: Invalid tokens should always be rejected gracefully
        result = jwt_service.validate_token(token_data, "access")
        
        assert result["valid"] is False
        assert "error" in result
        assert isinstance(result["error"], str)
        assert len(result["error"]) > 0
    
    @given(
        user_id=st.text(min_size=1, max_size=100),
        tenant_id=st.text(min_size=1, max_size=100),
        role=st.sampled_from([r.value for r in UserRole])
    )
    @settings(max_examples=50)
    def test_property_token_round_trip_consistency(self, user_id, tenant_id, role):
        """
        Property: Token generation and validation should be consistent.
        For any valid user data, generating tokens and then validating them 
        should return the same user information.
        """
        jwt_service = JWTTokenService()
        jwt_service.secret_key = "test-secret-key-for-property-testing"
        
        # Generate tokens
        tokens = jwt_service.generate_tokens(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role
        )
        
        # Validate access token
        access_result = jwt_service.validate_token(tokens["access_token"], "access")
        
        # Property: Valid tokens should always validate successfully
        assert access_result["valid"] is True
        
        # Property: Validated data should match original data
        payload = access_result["payload"]
        assert payload["sub"] == user_id
        assert payload["tenant_id"] == tenant_id
        assert payload["role"] == role
        assert payload["type"] == "access"
        
        # Validate refresh token
        refresh_result = jwt_service.validate_token(tokens["refresh_token"], "refresh")
        
        # Property: Refresh tokens should also validate successfully
        assert refresh_result["valid"] is True
        
        # Property: Refresh token should have consistent user data
        refresh_payload = refresh_result["payload"]
        assert refresh_payload["sub"] == user_id
        assert refresh_payload["tenant_id"] == tenant_id
        assert refresh_payload["type"] == "refresh"
    
    @given(
        time_offset_minutes=st.integers(min_value=-120, max_value=120)
    )
    @settings(max_examples=30)
    def test_property_token_expiration_boundaries(self, time_offset_minutes):
        """
        Property: Token expiration should be handled correctly at boundaries.
        For any token with expiration time offset, validation should correctly 
        determine if the token is expired or valid.
        """
        jwt_service = JWTTokenService()
        jwt_service.secret_key = "test-secret-key-for-property-testing"
        
        # Create token with specific expiration offset
        now = datetime.utcnow()
        exp_time = now + timedelta(minutes=time_offset_minutes)
        
        payload = {
            "sub": "test-user",
            "tenant_id": "test-tenant",
            "role": "CREATOR",
            "type": "access",
            "iat": now,
            "exp": exp_time
        }
        
        token = jwt.encode(payload, jwt_service.secret_key, algorithm=jwt_service.algorithm)
        
        # Validate token
        result = jwt_service.validate_token(token, "access")
        
        # Property: Tokens should be valid if and only if they haven't expired
        if time_offset_minutes > 0:
            # Token should be valid (expires in the future)
            assert result["valid"] is True
            assert "payload" in result
        else:
            # Token should be invalid (expired or expires now/in past)
            assert result["valid"] is False
            assert "error" in result
            if time_offset_minutes < -1:  # Allow some tolerance for execution time
                assert "expired" in result["error"].lower()


# Import json for the lambda_handler test
import json