"""
AI Stack for Nexora AI Platform.

This stack creates AI-related resources including:
- Lambda functions for AI services
- IAM roles for Bedrock access
- Lambda layers for shared dependencies
"""

from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_lambda_python_alpha as lambda_python,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .data_stack import DataStack


class AiStack(Stack):
    """Stack for AI services and Lambda functions."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stage: str,
        data_stack: "DataStack",
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.stage = stage
        self.data_stack = data_stack

        # Create shared Lambda layer
        self._create_lambda_layer()

        # Create IAM roles
        self._create_iam_roles()

        # Create Lambda functions
        self._create_lambda_functions()

    def _create_lambda_layer(self) -> None:
        """Create shared Lambda layer with common dependencies."""
        
        self.shared_layer = lambda_python.PythonLayerVersion(
            self,
            "SharedLayer",
            entry="../src/layers/shared",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_9],
            description="Shared dependencies for Nexora AI Lambda functions",
            removal_policy=lambda_.RemovalPolicy.DESTROY if self.stage == "dev" else lambda_.RemovalPolicy.RETAIN,
        )

    def _create_iam_roles(self) -> None:
        """Create IAM roles for Lambda functions."""
        
        # Base execution role for all Lambda functions
        self.lambda_execution_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole"),
            ],
            inline_policies={
                "NexoraLambdaPolicy": iam.PolicyDocument(
                    statements=[
                        # DynamoDB access
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "dynamodb:GetItem",
                                "dynamodb:PutItem",
                                "dynamodb:UpdateItem",
                                "dynamodb:DeleteItem",
                                "dynamodb:Query",
                                "dynamodb:Scan",
                                "dynamodb:BatchGetItem",
                                "dynamodb:BatchWriteItem",
                            ],
                            resources=[
                                self.data_stack.users_table.table_arn,
                                self.data_stack.tenants_table.table_arn,
                                self.data_stack.content_requests_table.table_arn,
                                self.data_stack.generated_content_table.table_arn,
                                self.data_stack.workflow_executions_table.table_arn,
                                self.data_stack.publications_table.table_arn,
                                f"{self.data_stack.users_table.table_arn}/index/*",
                                f"{self.data_stack.content_requests_table.table_arn}/index/*",
                                f"{self.data_stack.generated_content_table.table_arn}/index/*",
                            ],
                        ),
                        # S3 access
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                                "s3:ListBucket",
                            ],
                            resources=[
                                self.data_stack.content_bucket.bucket_arn,
                                f"{self.data_stack.content_bucket.bucket_arn}/*",
                                self.data_stack.analytics_bucket.bucket_arn,
                                f"{self.data_stack.analytics_bucket.bucket_arn}/*",
                            ],
                        ),
                        # OpenSearch Serverless access
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "aoss:APIAccessAll",
                            ],
                            resources=[
                                f"arn:aws:aoss:{self.region}:{self.account}:collection/*",
                            ],
                        ),
                        # Bedrock access
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/*",
                            ],
                        ),
                        # CloudWatch Logs
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            resources=["*"],
                        ),
                        # X-Ray tracing
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "xray:PutTraceSegments",
                                "xray:PutTelemetryRecords",
                            ],
                            resources=["*"],
                        ),
                    ]
                )
            },
        )

    def _create_lambda_functions(self) -> None:
        """Create Lambda functions for AI services."""
        
        # Common Lambda configuration
        common_config = {
            "runtime": lambda_.Runtime.PYTHON_3_9,
            "timeout": Duration.minutes(15),
            "memory_size": 1024,
            "role": self.lambda_execution_role,
            "layers": [self.shared_layer],
            "environment": {
                "STAGE": self.stage,
                "USERS_TABLE": self.data_stack.users_table.table_name,
                "TENANTS_TABLE": self.data_stack.tenants_table.table_name,
                "CONTENT_REQUESTS_TABLE": self.data_stack.content_requests_table.table_name,
                "GENERATED_CONTENT_TABLE": self.data_stack.generated_content_table.table_name,
                "WORKFLOW_EXECUTIONS_TABLE": self.data_stack.workflow_executions_table.table_name,
                "PUBLICATIONS_TABLE": self.data_stack.publications_table.table_name,
                "CONTENT_BUCKET": self.data_stack.content_bucket.bucket_name,
                "ANALYTICS_BUCKET": self.data_stack.analytics_bucket.bucket_name,
                "OPENSEARCH_ENDPOINT": self.data_stack.opensearch_collection.attr_collection_endpoint,
            },
            "tracing": lambda_.Tracing.ACTIVE,
            "log_retention": logs.RetentionDays.ONE_WEEK if self.stage == "dev" else logs.RetentionDays.ONE_MONTH,
        }

        # Content Generation Service
        self.content_generation_function = lambda_python.PythonFunction(
            self,
            "ContentGenerationFunction",
            entry="../src/services/content_generation",
            handler="handler.lambda_handler",
            function_name=f"nexora-content-generation-{self.stage}",
            description="Handles AI content generation using LangChain and Bedrock",
            **common_config,
        )

        # RAG Pipeline Service
        self.rag_pipeline_function = lambda_python.PythonFunction(
            self,
            "RagPipelineFunction",
            entry="../src/services/rag_pipeline",
            handler="handler.lambda_handler",
            function_name=f"nexora-rag-pipeline-{self.stage}",
            description="Handles document ingestion and RAG context retrieval",
            timeout=Duration.minutes(10),
            memory_size=2048,  # More memory for embedding generation
            **{k: v for k, v in common_config.items() if k not in ["timeout", "memory_size"]},
        )

        # Automation Controller Service
        self.automation_controller_function = lambda_python.PythonFunction(
            self,
            "AutomationControllerFunction",
            entry="../src/services/automation_controller",
            handler="handler.lambda_handler",
            function_name=f"nexora-automation-controller-{self.stage}",
            description="Manages workflow automation and human review processes",
            **common_config,
        )

        # Publishing Service
        self.publishing_function = lambda_python.PythonFunction(
            self,
            "PublishingFunction",
            entry="../src/services/publishing",
            handler="handler.lambda_handler",
            function_name=f"nexora-publishing-{self.stage}",
            description="Handles content publishing to external platforms",
            **common_config,
        )

        # Analytics Service
        self.analytics_function = lambda_python.PythonFunction(
            self,
            "AnalyticsFunction",
            entry="../src/services/analytics",
            handler="handler.lambda_handler",
            function_name=f"nexora-analytics-{self.stage}",
            description="Collects and processes analytics data",
            **common_config,
        )

        # Tenant Management Service
        self.tenant_management_function = lambda_python.PythonFunction(
            self,
            "TenantManagementFunction",
            entry="../src/services/tenant_management",
            handler="handler.lambda_handler",
            function_name=f"nexora-tenant-management-{self.stage}",
            description="Manages multi-tenant operations and resource quotas",
            **common_config,
        )

        # Responsible AI Service
        self.responsible_ai_function = lambda_python.PythonFunction(
            self,
            "ResponsibleAiFunction",
            entry="../src/services/responsible_ai",
            handler="handler.lambda_handler",
            function_name=f"nexora-responsible-ai-{self.stage}",
            description="Handles content filtering and bias detection",
            **common_config,
        )