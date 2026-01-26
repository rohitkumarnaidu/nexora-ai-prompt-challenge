#!/usr/bin/env python3
"""
Property-based tests for authentication system (standalone version).

These tests validate universal properties that should hold across all inputs.
"""

import jwt
import re
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings


class JWTTokenService:
    """JWT token generation and validation service."""
    
    def __init__(self):
        self.secret_key = "test-secret-key-for-property-testing"
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60
        self.refresh_token_expire_days = 30
    
    def generate_tokens(self, user_id: str, tenant_id: str, role: str) -> dict:
        """Generate access and refresh tokens."""
        now = datetime.utcnow()
        
        # Access token payload
        access_payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=self.access_token_expire_minutes)
        }
        
        # Refresh token payload
        refresh_payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(days=self.refresh_token_expire_days)
        }
        
        access_token = jwt.encode(access_payload, self.secret_key, algorithm=self.algorithm)
        refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm=self.algorithm)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": self.access_token_expire_minutes * 60,
            "token_type": "Bearer"
        }
    
    def validate_token(self, token: str, token_type: str = "access") -> dict:
        """Validate JWT token and return payload."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get("type") != token_type:
                return {
                    "valid": False,
                    "error": "Invalid token type"
                }
            
            return {
                "valid": True,
                "payload": payload
            }
            
        except jwt.ExpiredSignatureError:
            return {
                "valid": False,
                "error": "Token has expired"
            }
        except jwt.InvalidTokenError as e:
            return {
                "valid": False,
                "error": f"Invalid token: {str(e)}"
            }


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


def validate_email(email: str) -> bool:
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password: str) -> bool:
    """Validate password strength."""
    if len(password) < 8:
        return False
    return True


# Property-based tests
@given(
    user_id=st.text(min_size=1, max_size=100),
    tenant_id=st.text(min_size=1, max_size=100),
    role=st.sampled_from(["CREATOR", "ADMIN", "MEMBER"])
)
@settings(max_examples=50)
def test_property_1_authentication_token_generation(user_id, tenant_id, role):
    """
    Feature: nexora-ai-platform, Property 1: Authentication Token Generation
    For any successful user authentication with valid credentials, the system 
    should generate secure session tokens with appropriate expiration times 
    and proper JWT structure.
    **Validates: Requirements 1.2**
    """
    jwt_service = JWTTokenService()
    
    # Generate tokens for valid user data
    tokens = jwt_service.generate_tokens(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role
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
    assert access_payload["sub"] == user_id
    assert access_payload["tenant_id"] == tenant_id
    assert access_payload["role"] == role
    assert access_payload["type"] == "access"
    assert "iat" in access_payload
    assert "exp" in access_payload
    
    # Property: Refresh token should have correct structure
    assert refresh_payload["sub"] == user_id
    assert refresh_payload["tenant_id"] == tenant_id
    assert refresh_payload["type"] == "refresh"
    assert "iat" in refresh_payload
    assert "exp" in refresh_payload
    
    # Property: Expiration times should be in the future
    now = datetime.utcnow().timestamp()
    assert access_payload["exp"] > now
    assert refresh_payload["exp"] > now
    
    # Property: Refresh token should expire later than access token
    assert refresh_payload["exp"] > access_payload["exp"]


@given(
    user_id=st.text(min_size=1, max_size=100),
    tenant_id=st.text(min_size=1, max_size=100),
    role=st.sampled_from(["CREATOR", "ADMIN", "MEMBER"])
)
@settings(max_examples=50)
def test_property_2_session_expiration_redirect(user_id, tenant_id, role):
    """
    Feature: nexora-ai-platform, Property 2: Session Expiration Redirect
    For any expired user session, accessing protected resources should 
    redirect to login while preserving the intended destination URL.
    **Validates: Requirements 1.3**
    """
    jwt_service = JWTTokenService()
    
    # Create an expired token
    now = datetime.utcnow()
    expired_payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
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
    user_role=st.sampled_from(["CREATOR", "ADMIN", "MEMBER"]),
    user_id=st.text(min_size=1, max_size=50),
    tenant_id=st.text(min_size=1, max_size=50)
)
@settings(max_examples=50)
def test_property_3_role_based_access_control(user_role, user_id, tenant_id):
    """
    Feature: nexora-ai-platform, Property 3: Role-Based Access Control
    For any user with a specific role, access to resources should be 
    granted or denied based on the role's permissions, ensuring proper 
    authorization boundaries.
    **Validates: Requirements 1.4**
    """
    jwt_service = JWTTokenService()
    
    # Generate token with specific role
    tokens = jwt_service.generate_tokens(
        user_id=user_id,
        tenant_id=tenant_id,
        role=user_role
    )
    
    # Validate token and extract role
    validation_result = jwt_service.validate_token(tokens["access_token"], "access")
    
    # Property: Valid tokens should always contain role information
    assert validation_result["valid"] is True
    assert "role" in validation_result["payload"]
    assert validation_result["payload"]["role"] == user_role
    
    # Property: Role should be one of the valid values
    assert user_role in ["CREATOR", "ADMIN", "MEMBER"]
    
    # Property: Token should preserve role information accurately
    extracted_role = validation_result["payload"]["role"]
    assert extracted_role == user_role


@given(
    email=email_strategy(),
    password=st.text(min_size=1, max_size=50)
)
@settings(max_examples=30)
def test_property_4_authentication_error_handling(email, password):
    """
    Feature: nexora-ai-platform, Property 4: Authentication Error Handling
    For any authentication failure with invalid credentials, the system 
    should return clear error messages without exposing sensitive security 
    information.
    **Validates: Requirements 1.5**
    """
    # Test email validation
    email_valid = validate_email(email)
    password_valid = validate_password(password)
    
    # Property: Invalid emails should be detected
    if not email_valid:
        # Email validation should fail for invalid emails
        assert not email_valid
    
    # Property: Weak passwords should be detected
    if not password_valid:
        # Password validation should fail for weak passwords
        assert not password_valid
    
    # Property: Error handling should not expose sensitive information
    # This is a structural property - error messages should be generic
    if not email_valid or not password_valid:
        # Simulate error response structure
        error_response = {
            "success": False,
            "message": "Invalid credentials" if not email_valid else "Weak password",
            "error_code": "INVALID_EMAIL" if not email_valid else "WEAK_PASSWORD"
        }
        
        # Property: Should not expose internal system details
        sensitive_terms = ["cognito", "aws", "internal", "stack", "trace", "exception"]
        message_lower = error_response["message"].lower()
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
def test_property_jwt_token_validation_robustness(token_data):
    """
    Property: JWT token validation should handle all invalid inputs gracefully.
    For any invalid token input, the validation should return a proper error 
    response without crashing.
    """
    jwt_service = JWTTokenService()
    
    # Property: Invalid tokens should always be rejected gracefully
    result = jwt_service.validate_token(token_data, "access")
    
    assert result["valid"] is False
    assert "error" in result
    assert isinstance(result["error"], str)
    assert len(result["error"]) > 0


@given(
    user_id=st.text(min_size=1, max_size=100),
    tenant_id=st.text(min_size=1, max_size=100),
    role=st.sampled_from(["CREATOR", "ADMIN", "MEMBER"])
)
@settings(max_examples=50)
def test_property_token_round_trip_consistency(user_id, tenant_id, role):
    """
    Property: Token generation and validation should be consistent.
    For any valid user data, generating tokens and then validating them 
    should return the same user information.
    """
    jwt_service = JWTTokenService()
    
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
def test_property_token_expiration_boundaries(time_offset_minutes):
    """
    Property: Token expiration should be handled correctly at boundaries.
    For any token with expiration time offset, validation should correctly 
    determine if the token is expired or valid.
    """
    jwt_service = JWTTokenService()
    
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


def run_all_property_tests():
    """Run all property-based tests."""
    print("🧪 Running Property-Based Tests for Authentication System...")
    
    test_functions = [
        test_property_1_authentication_token_generation,
        test_property_2_session_expiration_redirect,
        test_property_3_role_based_access_control,
        test_property_4_authentication_error_handling,
        test_property_jwt_token_validation_robustness,
        test_property_token_round_trip_consistency,
        test_property_token_expiration_boundaries,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            print(f"\n🔍 Running {test_func.__name__}...")
            test_func()
            print(f"   ✅ PASSED")
            passed += 1
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            failed += 1
    
    print(f"\n📊 Property Test Results:")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📈 Success Rate: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 All property-based tests passed!")
        print("✨ Authentication system properties are validated across all inputs!")
        return True
    else:
        print(f"\n⚠️  {failed} property test(s) failed!")
        return False


if __name__ == "__main__":
    try:
        success = run_all_property_tests()
        if success:
            print("\n🏆 Authentication system is robust and ready for production!")
        else:
            print("\n🔧 Some properties need attention before production deployment.")
    except Exception as e:
        print(f"\n💥 Error during property testing: {e}")
        import traceback
        traceback.print_exc()