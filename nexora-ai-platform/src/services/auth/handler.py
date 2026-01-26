"""
Authentication service Lambda handler.

Handles AWS Cognito integration, JWT token management, and user authentication.
"""

import json
import jwt
import boto3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import structlog
from botocore.exceptions import ClientError

from ...shared.models import User, Tenant, UserRole, TenantType, SubscriptionTier
from ...shared.utils import (
    create_api_response,
    parse_lambda_event,
    get_correlation_id,
    get_dynamodb_resource,
    handle_aws_error,
    AWSClientManager,
    validate_email,
    utc_now,
)
from ...shared.config import settings

logger = structlog.get_logger()


class CognitoAuthService:
    """AWS Cognito authentication service."""
    
    def __init__(self):
        self.cognito_client = AWSClientManager.get_client("cognito-idp")
        self.user_pool_id = settings.user_pool_id
        self.client_id = settings.user_pool_client_id
        
    def register_user(
        self, 
        email: str, 
        password: str, 
        first_name: str, 
        last_name: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Register a new user in Cognito."""
        try:
            response = self.cognito_client.admin_create_user(
                UserPoolId=self.user_pool_id,
                Username=email,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "email_verified", "Value": "true"},
                    {"Name": "given_name", "Value": first_name},
                    {"Name": "family_name", "Value": last_name},
                    {"Name": "custom:tenant_id", "Value": tenant_id},
                ],
                TemporaryPassword=password,
                MessageAction="SUPPRESS",  # Don't send welcome email
            )
            
            # Set permanent password
            self.cognito_client.admin_set_user_password(
                UserPoolId=self.user_pool_id,
                Username=email,
                Password=password,
                Permanent=True
            )
            
            return {
                "success": True,
                "cognito_sub": response["User"]["Username"],
                "user_status": response["User"]["UserStatus"]
            }
            
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            
            logger.error(
                "Cognito user registration failed",
                error_code=error_code,
                error_message=error_message,
                email=email
            )
            
            return {
                "success": False,
                "error_code": error_code,
                "error_message": error_message
            }
    
    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user with Cognito."""
        try:
            response = self.cognito_client.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.client_id,
                AuthFlow="ADMIN_NO_SRP_AUTH",
                AuthParameters={
                    "USERNAME": email,
                    "PASSWORD": password,
                }
            )
            
            if "ChallengeName" in response:
                return {
                    "success": False,
                    "error_code": "CHALLENGE_REQUIRED",
                    "challenge_name": response["ChallengeName"],
                    "session": response.get("Session")
                }
            
            auth_result = response["AuthenticationResult"]
            
            # Decode the ID token to get user info
            id_token = auth_result["IdToken"]
            user_info = jwt.decode(id_token, options={"verify_signature": False})
            
            return {
                "success": True,
                "access_token": auth_result["AccessToken"],
                "id_token": id_token,
                "refresh_token": auth_result["RefreshToken"],
                "expires_in": auth_result["ExpiresIn"],
                "token_type": auth_result["TokenType"],
                "cognito_sub": user_info["sub"],
                "email": user_info["email"],
                "tenant_id": user_info.get("custom:tenant_id")
            }
            
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            
            logger.error(
                "Cognito authentication failed",
                error_code=error_code,
                error_message=error_message,
                email=email
            )
            
            return {
                "success": False,
                "error_code": error_code,
                "error_message": error_message
            }
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token."""
        try:
            response = self.cognito_client.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.client_id,
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters={
                    "REFRESH_TOKEN": refresh_token,
                }
            )
            
            auth_result = response["AuthenticationResult"]
            
            return {
                "success": True,
                "access_token": auth_result["AccessToken"],
                "id_token": auth_result["IdToken"],
                "expires_in": auth_result["ExpiresIn"],
                "token_type": auth_result["TokenType"]
            }
            
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            
            logger.error(
                "Token refresh failed",
                error_code=error_code,
                error_message=error_message
            )
            
            return {
                "success": False,
                "error_code": error_code,
                "error_message": error_message
            }
    
    def validate_token(self, access_token: str) -> Dict[str, Any]:
        """Validate access token and return user info."""
        try:
            response = self.cognito_client.get_user(AccessToken=access_token)
            
            user_attributes = {attr["Name"]: attr["Value"] for attr in response["UserAttributes"]}
            
            return {
                "success": True,
                "username": response["Username"],
                "user_attributes": user_attributes,
                "cognito_sub": user_attributes.get("sub"),
                "email": user_attributes.get("email"),
                "tenant_id": user_attributes.get("custom:tenant_id")
            }
            
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            
            logger.error(
                "Token validation failed",
                error_code=error_code,
                error_message=error_message
            )
            
            return {
                "success": False,
                "error_code": error_code,
                "error_message": error_message
            }
    
    def initiate_google_auth(self, redirect_uri: str) -> str:
        """Generate Google OAuth URL for authentication."""
        domain = f"nexora-auth-{settings.stage}"
        
        google_auth_url = (
            f"https://{domain}.auth.{settings.aws_region}.amazoncognito.com/oauth2/authorize"
            f"?client_id={self.client_id}"
            f"&response_type=code"
            f"&scope=email+openid+profile"
            f"&redirect_uri={redirect_uri}"
            f"&identity_provider=Google"
        )
        
        return google_auth_url
    
    def handle_oauth_callback(self, authorization_code: str, redirect_uri: str) -> Dict[str, Any]:
        """Handle OAuth callback and exchange code for tokens."""
        try:
            import requests
            
            domain = f"nexora-auth-{settings.stage}"
            token_url = f"https://{domain}.auth.{settings.aws_region}.amazoncognito.com/oauth2/token"
            
            response = requests.post(
                token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "code": authorization_code,
                    "redirect_uri": redirect_uri,
                }
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Decode ID token to get user info
                id_token = token_data["id_token"]
                user_info = jwt.decode(id_token, options={"verify_signature": False})
                
                return {
                    "success": True,
                    "access_token": token_data["access_token"],
                    "id_token": id_token,
                    "refresh_token": token_data["refresh_token"],
                    "expires_in": token_data["expires_in"],
                    "token_type": token_data["token_type"],
                    "cognito_sub": user_info["sub"],
                    "email": user_info["email"],
                    "tenant_id": user_info.get("custom:tenant_id")
                }
            else:
                return {
                    "success": False,
                    "error_code": "OAUTH_EXCHANGE_FAILED",
                    "error_message": response.text
                }
                
        except Exception as e:
            logger.error("OAuth callback handling failed", error=str(e))
            return {
                "success": False,
                "error_code": "OAUTH_CALLBACK_ERROR",
                "error_message": str(e)
            }


class JWTTokenService:
    """JWT token generation and validation service."""
    
    def __init__(self):
        self.secret_key = settings.jwt_secret_key or "default-secret-key"
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60
        self.refresh_token_expire_days = 30
    
    def generate_tokens(self, user_id: str, tenant_id: str, role: str) -> Dict[str, Any]:
        """Generate access and refresh tokens."""
        now = utc_now()
        
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
    
    def validate_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
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


# Initialize services
cognito_service = CognitoAuthService()
jwt_service = JWTTokenService()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for authentication service."""
    correlation_id = get_correlation_id(event)
    logger.info("Authentication request received", correlation_id=correlation_id)
    
    try:
        # Parse event
        parsed_event = parse_lambda_event(event)
        http_method = parsed_event["http_method"]
        path = parsed_event["path"]
        body = parsed_event["body"]
        
        # Route to appropriate handler
        if http_method == "POST":
            if path.endswith("/auth/register"):
                return handle_user_registration(body, correlation_id)
            elif path.endswith("/auth/login"):
                return handle_user_login(body, correlation_id)
            elif path.endswith("/auth/refresh"):
                return handle_token_refresh(body, correlation_id)
            elif path.endswith("/auth/validate"):
                return handle_token_validation(body, correlation_id)
            elif path.endswith("/auth/google"):
                return handle_google_auth(body, correlation_id)
            elif path.endswith("/auth/google/callback"):
                return handle_google_callback(body, correlation_id)
        
        return create_api_response(
            success=False,
            message="Invalid request",
            error_code="INVALID_REQUEST",
            status_code=400,
        )
        
    except Exception as e:
        logger.error("Authentication error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Internal server error",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )


def handle_user_registration(body: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Handle user registration with Cognito integration."""
    try:
        # Extract registration data
        email = body.get("email")
        password = body.get("password")
        first_name = body.get("first_name")
        last_name = body.get("last_name")
        tenant_name = body.get("tenant_name")
        tenant_type = body.get("tenant_type", "INDIVIDUAL")
        
        # Validate required fields
        if not all([email, password, first_name, last_name]):
            return create_api_response(
                success=False,
                message="Missing required fields: email, password, first_name, last_name",
                error_code="MISSING_FIELDS",
                status_code=400,
            )
        
        # Validate email format
        if not validate_email(email):
            return create_api_response(
                success=False,
                message="Invalid email format",
                error_code="INVALID_EMAIL",
                status_code=400,
            )
        
        # Validate password strength (basic validation)
        if len(password) < 8:
            return create_api_response(
                success=False,
                message="Password must be at least 8 characters long",
                error_code="WEAK_PASSWORD",
                status_code=400,
            )
        
        # Create tenant first
        tenant = Tenant(
            name=tenant_name or f"{first_name} {last_name}",
            type=TenantType(tenant_type),
            subscription_tier=SubscriptionTier.FREE,
        )
        
        # Register user in Cognito
        cognito_result = cognito_service.register_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            tenant_id=tenant.tenant_id
        )
        
        if not cognito_result["success"]:
            return create_api_response(
                success=False,
                message=f"Registration failed: {cognito_result['error_message']}",
                error_code=cognito_result["error_code"],
                status_code=400,
            )
        
        # Create user record
        user = User(
            email=email,
            cognito_sub=cognito_result["cognito_sub"],
            tenant_id=tenant.tenant_id,
            role=UserRole.ADMIN,  # First user in tenant is admin
            first_name=first_name,
            last_name=last_name,
        )
        
        # Save to DynamoDB
        dynamodb = get_dynamodb_resource()
        
        # Save tenant
        tenants_table = dynamodb.Table(settings.tenants_table)
        tenants_table.put_item(Item=tenant.dict())
        
        # Save user
        users_table = dynamodb.Table(settings.users_table)
        users_table.put_item(Item=user.dict())
        
        # Generate JWT tokens
        tokens = jwt_service.generate_tokens(
            user_id=user.user_id,
            tenant_id=tenant.tenant_id,
            role=user.role.value
        )
        
        logger.info(
            "User registration successful",
            user_id=user.user_id,
            tenant_id=tenant.tenant_id,
            correlation_id=correlation_id,
        )
        
        return create_api_response(
            success=True,
            message="Registration successful",
            data={
                "user": {
                    "user_id": user.user_id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "tenant_id": tenant.tenant_id,
                    "role": user.role.value,
                },
                "tokens": tokens,
            },
        )
        
    except Exception as e:
        logger.error("Registration error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Registration failed",
            error_code="REGISTRATION_FAILED",
            status_code=500,
        )


def handle_user_login(body: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Handle user login with Cognito authentication."""
    try:
        email = body.get("email")
        password = body.get("password")
        
        if not all([email, password]):
            return create_api_response(
                success=False,
                message="Missing email or password",
                error_code="MISSING_CREDENTIALS",
                status_code=400,
            )
        
        # Authenticate with Cognito
        auth_result = cognito_service.authenticate_user(email, password)
        
        if not auth_result["success"]:
            return create_api_response(
                success=False,
                message=f"Authentication failed: {auth_result['error_message']}",
                error_code=auth_result["error_code"],
                status_code=401,
            )
        
        # Look up user in DynamoDB
        dynamodb = get_dynamodb_resource()
        users_table = dynamodb.Table(settings.users_table)
        
        # Query by cognito_sub (would need GSI in production)
        response = users_table.scan(
            FilterExpression="cognito_sub = :sub",
            ExpressionAttributeValues={":sub": auth_result["cognito_sub"]}
        )
        
        if not response["Items"]:
            return create_api_response(
                success=False,
                message="User not found in system",
                error_code="USER_NOT_FOUND",
                status_code=404,
            )
        
        user_data = response["Items"][0]
        
        # Update last login
        users_table.update_item(
            Key={"user_id": user_data["user_id"]},
            UpdateExpression="SET last_login = :timestamp",
            ExpressionAttributeValues={":timestamp": utc_now().isoformat()},
        )
        
        # Generate JWT tokens
        tokens = jwt_service.generate_tokens(
            user_id=user_data["user_id"],
            tenant_id=user_data["tenant_id"],
            role=user_data["role"]
        )
        
        logger.info(
            "User login successful",
            user_id=user_data["user_id"],
            tenant_id=user_data["tenant_id"],
            correlation_id=correlation_id,
        )
        
        return create_api_response(
            success=True,
            message="Login successful",
            data={
                "user": {
                    "user_id": user_data["user_id"],
                    "email": user_data["email"],
                    "first_name": user_data["first_name"],
                    "last_name": user_data["last_name"],
                    "tenant_id": user_data["tenant_id"],
                    "role": user_data["role"],
                },
                "tokens": tokens,
                "cognito_tokens": {
                    "access_token": auth_result["access_token"],
                    "id_token": auth_result["id_token"],
                    "refresh_token": auth_result["refresh_token"],
                }
            },
        )
        
    except Exception as e:
        logger.error("Login error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Login failed",
            error_code="LOGIN_FAILED",
            status_code=500,
        )


def handle_token_refresh(body: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Handle token refresh using Cognito refresh token."""
    try:
        refresh_token = body.get("refresh_token")
        jwt_refresh_token = body.get("jwt_refresh_token")
        
        if not refresh_token and not jwt_refresh_token:
            return create_api_response(
                success=False,
                message="Missing refresh token",
                error_code="MISSING_REFRESH_TOKEN",
                status_code=400,
            )
        
        # If JWT refresh token is provided, use it
        if jwt_refresh_token:
            validation_result = jwt_service.validate_token(jwt_refresh_token, "refresh")
            
            if not validation_result["valid"]:
                return create_api_response(
                    success=False,
                    message=f"Invalid refresh token: {validation_result['error']}",
                    error_code="INVALID_REFRESH_TOKEN",
                    status_code=401,
                )
            
            payload = validation_result["payload"]
            
            # Generate new tokens
            tokens = jwt_service.generate_tokens(
                user_id=payload["sub"],
                tenant_id=payload["tenant_id"],
                role=payload.get("role", "CREATOR")
            )
            
            return create_api_response(
                success=True,
                message="Token refresh successful",
                data={"tokens": tokens},
            )
        
        # Otherwise, use Cognito refresh token
        refresh_result = cognito_service.refresh_token(refresh_token)
        
        if not refresh_result["success"]:
            return create_api_response(
                success=False,
                message=f"Token refresh failed: {refresh_result['error_message']}",
                error_code=refresh_result["error_code"],
                status_code=401,
            )
        
        return create_api_response(
            success=True,
            message="Token refresh successful",
            data={
                "cognito_tokens": {
                    "access_token": refresh_result["access_token"],
                    "id_token": refresh_result["id_token"],
                }
            },
        )
        
    except Exception as e:
        logger.error("Token refresh error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Token refresh failed",
            error_code="REFRESH_FAILED",
            status_code=500,
        )


def handle_token_validation(body: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Handle token validation."""
    try:
        access_token = body.get("access_token")
        jwt_token = body.get("jwt_token")
        
        if not access_token and not jwt_token:
            return create_api_response(
                success=False,
                message="Missing access token",
                error_code="MISSING_ACCESS_TOKEN",
                status_code=400,
            )
        
        # If JWT token is provided, validate it
        if jwt_token:
            validation_result = jwt_service.validate_token(jwt_token, "access")
            
            if not validation_result["valid"]:
                return create_api_response(
                    success=False,
                    message=f"Invalid token: {validation_result['error']}",
                    error_code="INVALID_TOKEN",
                    status_code=401,
                )
            
            return create_api_response(
                success=True,
                message="Token is valid",
                data={"payload": validation_result["payload"]},
            )
        
        # Otherwise, validate Cognito token
        validation_result = cognito_service.validate_token(access_token)
        
        if not validation_result["success"]:
            return create_api_response(
                success=False,
                message=f"Token validation failed: {validation_result['error_message']}",
                error_code=validation_result["error_code"],
                status_code=401,
            )
        
        return create_api_response(
            success=True,
            message="Token is valid",
            data={
                "user_info": {
                    "cognito_sub": validation_result["cognito_sub"],
                    "email": validation_result["email"],
                    "tenant_id": validation_result["tenant_id"],
                }
            },
        )
        
    except Exception as e:
        logger.error("Token validation error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Token validation failed",
            error_code="VALIDATION_FAILED",
            status_code=500,
        )


def handle_google_auth(body: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Handle Google OAuth initiation."""
    try:
        redirect_uri = body.get("redirect_uri")
        
        if not redirect_uri:
            return create_api_response(
                success=False,
                message="Missing redirect_uri",
                error_code="MISSING_REDIRECT_URI",
                status_code=400,
            )
        
        google_auth_url = cognito_service.initiate_google_auth(redirect_uri)
        
        return create_api_response(
            success=True,
            message="Google auth URL generated",
            data={"auth_url": google_auth_url},
        )
        
    except Exception as e:
        logger.error("Google auth error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Google auth failed",
            error_code="GOOGLE_AUTH_FAILED",
            status_code=500,
        )


def handle_google_callback(body: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Handle Google OAuth callback."""
    try:
        authorization_code = body.get("code")
        redirect_uri = body.get("redirect_uri")
        
        if not all([authorization_code, redirect_uri]):
            return create_api_response(
                success=False,
                message="Missing authorization code or redirect URI",
                error_code="MISSING_OAUTH_PARAMS",
                status_code=400,
            )
        
        # Exchange code for tokens
        callback_result = cognito_service.handle_oauth_callback(authorization_code, redirect_uri)
        
        if not callback_result["success"]:
            return create_api_response(
                success=False,
                message=f"OAuth callback failed: {callback_result['error_message']}",
                error_code=callback_result["error_code"],
                status_code=400,
            )
        
        # Check if user exists in our system
        dynamodb = get_dynamodb_resource()
        users_table = dynamodb.Table(settings.users_table)
        
        response = users_table.scan(
            FilterExpression="cognito_sub = :sub",
            ExpressionAttributeValues={":sub": callback_result["cognito_sub"]}
        )
        
        if response["Items"]:
            # Existing user - update last login
            user_data = response["Items"][0]
            
            users_table.update_item(
                Key={"user_id": user_data["user_id"]},
                UpdateExpression="SET last_login = :timestamp",
                ExpressionAttributeValues={":timestamp": utc_now().isoformat()},
            )
            
            # Generate JWT tokens
            tokens = jwt_service.generate_tokens(
                user_id=user_data["user_id"],
                tenant_id=user_data["tenant_id"],
                role=user_data["role"]
            )
            
            return create_api_response(
                success=True,
                message="Google login successful",
                data={
                    "user": {
                        "user_id": user_data["user_id"],
                        "email": user_data["email"],
                        "first_name": user_data["first_name"],
                        "last_name": user_data["last_name"],
                        "tenant_id": user_data["tenant_id"],
                        "role": user_data["role"],
                    },
                    "tokens": tokens,
                    "cognito_tokens": {
                        "access_token": callback_result["access_token"],
                        "id_token": callback_result["id_token"],
                        "refresh_token": callback_result["refresh_token"],
                    }
                },
            )
        else:
            # New user - need to complete registration
            return create_api_response(
                success=True,
                message="New Google user - registration required",
                data={
                    "new_user": True,
                    "email": callback_result["email"],
                    "cognito_sub": callback_result["cognito_sub"],
                    "cognito_tokens": {
                        "access_token": callback_result["access_token"],
                        "id_token": callback_result["id_token"],
                        "refresh_token": callback_result["refresh_token"],
                    }
                },
            )
        
    except Exception as e:
        logger.error("Google callback error", error=str(e), correlation_id=correlation_id)
        return create_api_response(
            success=False,
            message="Google callback failed",
            error_code="GOOGLE_CALLBACK_FAILED",
            status_code=500,
        )