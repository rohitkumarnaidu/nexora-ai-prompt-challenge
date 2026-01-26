"""
Authentication Stack for Nexora AI Platform.

This stack creates AWS Cognito resources for user authentication:
- User Pool for user management
- User Pool Client for application integration
- Identity Pool for AWS resource access
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_cognito as cognito,
    aws_iam as iam,
)
from constructs import Construct


class AuthStack(Stack):
    """Stack for authentication resources."""

    def __init__(self, scope: Construct, construct_id: str, stage: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.stage = stage

        # Create Cognito User Pool
        self._create_user_pool()

        # Create Identity Pool
        self._create_identity_pool()

    def _create_user_pool(self) -> None:
        """Create Cognito User Pool for user authentication."""
        
        self.user_pool = cognito.UserPool(
            self,
            "NexoraUserPool",
            user_pool_name=f"nexora-users-{self.stage}",
            removal_policy=RemovalPolicy.DESTROY if self.stage == "dev" else RemovalPolicy.RETAIN,
            
            # Sign-in configuration
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=False,
            ),
            
            # User attributes
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                given_name=cognito.StandardAttribute(required=True, mutable=True),
                family_name=cognito.StandardAttribute(required=True, mutable=True),
            ),
            
            custom_attributes={
                "tenant_id": cognito.StringAttribute(min_len=1, max_len=256, mutable=True),
                "user_role": cognito.StringAttribute(min_len=1, max_len=50, mutable=True),
            },
            
            # Password policy
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            
            # Account recovery
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            
            # Email configuration
            email=cognito.UserPoolEmail.with_cognito(),
            
            # Auto verification
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            
            # User invitation
            user_invitation=cognito.UserInvitationConfig(
                email_subject="Welcome to Nexora AI Platform",
                email_body="Hello {username}, you have been invited to join Nexora AI Platform. Your temporary password is {####}",
            ),
            
            # Device tracking
            device_tracking=cognito.DeviceTracking(
                challenge_required_on_new_device=True,
                device_only_remembered_on_user_prompt=True,
            ),
            
            # MFA configuration
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(
                sms=True,
                otp=True,
            ),
            
            # Lambda triggers (can be added later)
            lambda_triggers=cognito.UserPoolTriggers(),
        )

        # Create User Pool Client
        self.user_pool_client = cognito.UserPoolClient(
            self,
            "NexoraUserPoolClient",
            user_pool=self.user_pool,
            user_pool_client_name=f"nexora-client-{self.stage}",
            
            # Authentication flows
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                custom=True,
                admin_user_password=True,
            ),
            
            # OAuth configuration
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=False,
                ),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=[
                    f"https://nexora-{self.stage}.example.com/auth/callback",
                    "http://localhost:3000/auth/callback",  # For development
                ],
                logout_urls=[
                    f"https://nexora-{self.stage}.example.com/auth/logout",
                    "http://localhost:3000/auth/logout",  # For development
                ],
            ),
            
            # Token validity
            access_token_validity=cognito.Duration.hours(1),
            id_token_validity=cognito.Duration.hours(1),
            refresh_token_validity=cognito.Duration.days(30),
            
            # Security
            generate_secret=False,  # For web applications
            prevent_user_existence_errors=True,
            
            # Supported identity providers
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO,
                cognito.UserPoolClientIdentityProvider.GOOGLE,
            ],
        )

        # Create User Pool Domain
        self.user_pool_domain = cognito.UserPoolDomain(
            self,
            "NexoraUserPoolDomain",
            user_pool=self.user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"nexora-auth-{self.stage}",
            ),
        )

        # Create Google Identity Provider
        self.google_provider = cognito.UserPoolIdentityProviderGoogle(
            self,
            "GoogleProvider",
            user_pool=self.user_pool,
            client_id="your-google-client-id",  # Replace with actual Google OAuth client ID
            client_secret="your-google-client-secret",  # Replace with actual Google OAuth client secret
            scopes=["email", "profile", "openid"],
            attribute_mapping=cognito.AttributeMapping(
                email=cognito.ProviderAttribute.GOOGLE_EMAIL,
                given_name=cognito.ProviderAttribute.GOOGLE_GIVEN_NAME,
                family_name=cognito.ProviderAttribute.GOOGLE_FAMILY_NAME,
            ),
        )

        # Update client to include Google provider
        self.user_pool_client.node.add_dependency(self.google_provider)

    def _create_identity_pool(self) -> None:
        """Create Cognito Identity Pool for AWS resource access."""
        
        self.identity_pool = cognito.CfnIdentityPool(
            self,
            "NexoraIdentityPool",
            identity_pool_name=f"nexora_identity_pool_{self.stage}",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=self.user_pool_client.user_pool_client_id,
                    provider_name=self.user_pool.user_pool_provider_name,
                    server_side_token_check=True,
                ),
            ],
        )

        # Create IAM roles for authenticated users
        self.authenticated_role = iam.Role(
            self,
            "AuthenticatedRole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                conditions={
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": self.identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    },
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            inline_policies={
                "NexoraUserPolicy": iam.PolicyDocument(
                    statements=[
                        # Allow users to access their own data in DynamoDB
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "dynamodb:GetItem",
                                "dynamodb:PutItem",
                                "dynamodb:UpdateItem",
                                "dynamodb:DeleteItem",
                                "dynamodb:Query",
                            ],
                            resources=[
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/nexora-*-{self.stage}",
                            ],
                            conditions={
                                "ForAllValues:StringEquals": {
                                    "dynamodb:LeadingKeys": ["${cognito-identity.amazonaws.com:sub}"]
                                }
                            },
                        ),
                        # Allow users to access their own S3 objects
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                            ],
                            resources=[
                                f"arn:aws:s3:::nexora-content-{self.stage}-{self.account}/tenants/${{cognito-identity.amazonaws.com:sub}}/*",
                            ],
                        ),
                        # Allow users to list their own S3 objects
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["s3:ListBucket"],
                            resources=[
                                f"arn:aws:s3:::nexora-content-{self.stage}-{self.account}",
                            ],
                            conditions={
                                "StringLike": {
                                    "s3:prefix": ["tenants/${cognito-identity.amazonaws.com:sub}/*"]
                                }
                            },
                        ),
                    ]
                )
            },
        )

        # Attach the role to the identity pool
        cognito.CfnIdentityPoolRoleAttachment(
            self,
            "IdentityPoolRoleAttachment",
            identity_pool_id=self.identity_pool.ref,
            roles={
                "authenticated": self.authenticated_role.role_arn,
            },
        )