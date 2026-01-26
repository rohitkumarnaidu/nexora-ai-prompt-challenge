"""
API Stack for Nexora AI Platform.

This stack creates the API Gateway and integrates it with Lambda functions
and authentication services.
"""

from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_cognito as cognito,
    aws_iam as iam,
)
from constructs import Construct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .auth_stack import AuthStack
    from .data_stack import DataStack
    from .ai_stack import AiStack


class ApiStack(Stack):
    """Stack for API Gateway and Lambda integrations."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stage: str,
        auth_stack: "AuthStack",
        data_stack: "DataStack",
        ai_stack: "AiStack",
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.stage = stage
        self.auth_stack = auth_stack
        self.data_stack = data_stack
        self.ai_stack = ai_stack

        # Create API Gateway
        self._create_api_gateway()

        # Create Cognito authorizer
        self._create_authorizer()

        # Create API resources and methods
        self._create_api_resources()

    def _create_api_gateway(self) -> None:
        """Create the main API Gateway."""
        
        self.api = apigateway.RestApi(
            self,
            "NexoraApi",
            rest_api_name=f"nexora-api-{self.stage}",
            description=f"Nexora AI Platform API - {self.stage}",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "X-Amz-Date",
                    "Authorization",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent",
                ],
            ),
            deploy_options=apigateway.StageOptions(
                stage_name=self.stage,
                throttling_rate_limit=1000,
                throttling_burst_limit=2000,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
            ),
            endpoint_configuration=apigateway.EndpointConfiguration(
                types=[apigateway.EndpointType.REGIONAL]
            ),
        )

    def _create_authorizer(self) -> None:
        """Create Cognito authorizer for API Gateway."""
        
        self.authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "NexoraAuthorizer",
            cognito_user_pools=[self.auth_stack.user_pool],
            authorizer_name=f"nexora-authorizer-{self.stage}",
            identity_source="method.request.header.Authorization",
        )

    def _create_api_resources(self) -> None:
        """Create API resources and methods."""
        
        # Health check endpoint (no auth required)
        health_resource = self.api.root.add_resource("health")
        health_resource.add_method(
            "GET",
            apigateway.MockIntegration(
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": '{"status": "healthy", "timestamp": "$context.requestTime"}'
                        },
                    )
                ],
                passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
                request_templates={
                    "application/json": '{"statusCode": 200}'
                },
            ),
            method_responses=[
                apigateway.MethodResponse(status_code="200")
            ],
        )

        # Authentication endpoints
        auth_resource = self.api.root.add_resource("auth")
        
        # User registration/login (handled by Cognito, but we might need custom logic)
        auth_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                handler=self._create_auth_function(),
                proxy=True,
            ),
        )

        # Protected API endpoints
        api_v1 = self.api.root.add_resource("api").add_resource("v1")

        # Content generation endpoints
        content_resource = api_v1.add_resource("content")
        
        # Generate content
        content_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.content_generation_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Get content by ID
        content_id_resource = content_resource.add_resource("{content_id}")
        content_id_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.content_generation_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Update content
        content_id_resource.add_method(
            "PUT",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.content_generation_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # RAG pipeline endpoints
        rag_resource = api_v1.add_resource("rag")
        
        # Upload documents
        documents_resource = rag_resource.add_resource("documents")
        documents_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.rag_pipeline_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # List documents
        documents_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.rag_pipeline_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Delete document
        document_id_resource = documents_resource.add_resource("{document_id}")
        document_id_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.rag_pipeline_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Workflow automation endpoints
        workflows_resource = api_v1.add_resource("workflows")
        
        # Create workflow
        workflows_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.automation_controller_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Get workflow status
        workflow_id_resource = workflows_resource.add_resource("{workflow_id}")
        workflow_id_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.automation_controller_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Human review endpoints
        reviews_resource = api_v1.add_resource("reviews")
        
        # Get pending reviews
        reviews_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.automation_controller_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Submit review decision
        review_id_resource = reviews_resource.add_resource("{review_id}")
        review_id_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.automation_controller_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Publishing endpoints
        publishing_resource = api_v1.add_resource("publishing")
        
        # Configure publishing endpoints
        endpoints_resource = publishing_resource.add_resource("endpoints")
        endpoints_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.publishing_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        endpoints_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.publishing_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Publish content
        publish_resource = publishing_resource.add_resource("publish")
        publish_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.publishing_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Analytics endpoints
        analytics_resource = api_v1.add_resource("analytics")
        
        # Get dashboard data
        dashboard_resource = analytics_resource.add_resource("dashboard")
        dashboard_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.analytics_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Get reports
        reports_resource = analytics_resource.add_resource("reports")
        reports_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.analytics_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Tenant management endpoints
        tenants_resource = api_v1.add_resource("tenants")
        
        # Get tenant info
        tenants_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.tenant_management_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Update tenant settings
        tenants_resource.add_method(
            "PUT",
            apigateway.LambdaIntegration(
                handler=self.ai_stack.tenant_management_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

    def _create_auth_function(self) -> lambda_.Function:
        """Create authentication Lambda function."""
        
        return lambda_.Function(
            self,
            "AuthFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../src/services/auth"),
            function_name=f"nexora-auth-{self.stage}",
            description="Handles custom authentication logic",
            environment={
                "STAGE": self.stage,
                "USER_POOL_ID": self.auth_stack.user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": self.auth_stack.user_pool_client.user_pool_client_id,
                "USERS_TABLE": self.data_stack.users_table.table_name,
                "TENANTS_TABLE": self.data_stack.tenants_table.table_name,
            },
            role=self.ai_stack.lambda_execution_role,
        )