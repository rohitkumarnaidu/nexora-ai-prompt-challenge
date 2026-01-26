#!/usr/bin/env python3
"""
Standalone JWT test without relative imports.
"""

import jwt
from datetime import datetime, timedelta


class JWTTokenService:
    """JWT token generation and validation service."""
    
    def __init__(self):
        self.secret_key = "test-secret-key-for-testing"
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


def test_jwt_functionality():
    """Test JWT token generation and validation."""
    print("🔐 Testing JWT Token Service...")
    
    # Initialize JWT service
    jwt_service = JWTTokenService()
    
    # Test token generation
    print("\n1. Testing token generation...")
    tokens = jwt_service.generate_tokens(
        user_id="test-user-123",
        tenant_id="test-tenant-123",
        role="CREATOR"
    )
    
    print(f"   ✓ Access token generated (length: {len(tokens['access_token'])})")
    print(f"   ✓ Refresh token generated (length: {len(tokens['refresh_token'])})")
    print(f"   ✓ Expires in: {tokens['expires_in']} seconds")
    print(f"   ✓ Token type: {tokens['token_type']}")
    
    # Test token validation
    print("\n2. Testing token validation...")
    
    # Validate access token
    access_result = jwt_service.validate_token(tokens["access_token"], "access")
    if access_result["valid"]:
        payload = access_result["payload"]
        print(f"   ✓ Access token is valid")
        print(f"   ✓ User ID: {payload['sub']}")
        print(f"   ✓ Tenant ID: {payload['tenant_id']}")
        print(f"   ✓ Role: {payload['role']}")
        print(f"   ✓ Token type: {payload['type']}")
    else:
        print(f"   ✗ Access token validation failed: {access_result['error']}")
        return False
    
    # Validate refresh token
    refresh_result = jwt_service.validate_token(tokens["refresh_token"], "refresh")
    if refresh_result["valid"]:
        payload = refresh_result["payload"]
        print(f"   ✓ Refresh token is valid")
        print(f"   ✓ User ID: {payload['sub']}")
        print(f"   ✓ Tenant ID: {payload['tenant_id']}")
        print(f"   ✓ Token type: {payload['type']}")
    else:
        print(f"   ✗ Refresh token validation failed: {refresh_result['error']}")
        return False
    
    # Test invalid token
    print("\n3. Testing invalid token handling...")
    invalid_result = jwt_service.validate_token("invalid.jwt.token", "access")
    if not invalid_result["valid"]:
        print(f"   ✓ Invalid token correctly rejected: {invalid_result['error']}")
    else:
        print(f"   ✗ Invalid token was incorrectly accepted")
        return False
    
    # Test wrong token type
    print("\n4. Testing wrong token type...")
    wrong_type_result = jwt_service.validate_token(tokens["access_token"], "refresh")
    if not wrong_type_result["valid"]:
        print(f"   ✓ Wrong token type correctly rejected: {wrong_type_result['error']}")
    else:
        print(f"   ✗ Wrong token type was incorrectly accepted")
        return False
    
    # Test expired token
    print("\n5. Testing expired token...")
    # Create an expired token
    now = datetime.utcnow()
    expired_payload = {
        "sub": "test-user",
        "tenant_id": "test-tenant",
        "role": "CREATOR",
        "type": "access",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1)  # Expired 1 hour ago
    }
    
    expired_token = jwt.encode(expired_payload, jwt_service.secret_key, algorithm=jwt_service.algorithm)
    expired_result = jwt_service.validate_token(expired_token, "access")
    
    if not expired_result["valid"] and "expired" in expired_result["error"].lower():
        print(f"   ✓ Expired token correctly rejected: {expired_result['error']}")
    else:
        print(f"   ✗ Expired token was incorrectly accepted")
        return False
    
    print("\n✅ All JWT tests passed!")
    return True


if __name__ == "__main__":
    try:
        success = test_jwt_functionality()
        if success:
            print("\n🎉 JWT Token Service is working correctly!")
            print("\n📋 Test Summary:")
            print("   ✓ Token generation")
            print("   ✓ Token validation")
            print("   ✓ Invalid token rejection")
            print("   ✓ Wrong token type rejection")
            print("   ✓ Expired token rejection")
            print("\n✨ Ready for integration with AWS Cognito!")
        else:
            print("\n❌ JWT Token Service tests failed!")
    except Exception as e:
        print(f"\n💥 Error during testing: {e}")
        import traceback
        traceback.print_exc()