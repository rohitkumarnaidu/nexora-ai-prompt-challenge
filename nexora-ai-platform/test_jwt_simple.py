#!/usr/bin/env python3
"""
Simple test script to verify JWT functionality.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set environment variables for testing
os.environ['STAGE'] = 'test'
os.environ['JWT_SECRET_KEY'] = 'test-secret-key-for-testing'

from services.auth.handler import JWTTokenService

def test_jwt_functionality():
    """Test JWT token generation and validation."""
    print("Testing JWT Token Service...")
    
    # Initialize JWT service
    jwt_service = JWTTokenService()
    jwt_service.secret_key = "test-secret-key"
    
    # Test token generation
    print("1. Testing token generation...")
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
    
    print("\n✅ All JWT tests passed!")
    return True

if __name__ == "__main__":
    try:
        success = test_jwt_functionality()
        if success:
            print("\n🎉 JWT Token Service is working correctly!")
            sys.exit(0)
        else:
            print("\n❌ JWT Token Service tests failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)