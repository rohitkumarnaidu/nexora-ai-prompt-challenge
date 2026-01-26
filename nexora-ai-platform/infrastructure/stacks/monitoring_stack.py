"""
Monitoring Stack for Nexora AI Platform.

This stack creates monitoring and observability resources including:
- CloudWatch dashboards
- Alarms and notifications
- X-Ray tracing configuration
"""

from aws_cdk import (
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
    aws_cloudwatch_actions as cw_actions,
    aws_logs as logs,
)
from constructs import Construct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .api_stack import ApiStack
    from .ai_stack import AiStack


class MonitoringStack(Stack):
    """Stack for monitoring and observability resources."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stage: str,
        api_stack: "ApiStack",
        ai_stack: "AiStack",
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.stage = stage
        self.api_stack = api_stack
        self.ai_stack = ai_stack

        # Create SNS topic for alerts
        self._create_alert_topic()

        # Create CloudWatch dashboard
        self._create_dashboard()

        # Create alarms
        self._create_alarms()

    def _create_alert_topic(self) -> None:
        """Create SNS topic for alert notifications."""
        
        self.alert_topic = sns.Topic(
            self,
            "AlertTopic",
            topic_name=f"nexora-alerts-{self.stage}",
            display_name=f"Nexora AI Platform Alerts - {self.stage}",
        )

        # Add email subscription (replace with actual email)
        self.alert_topic.add_subscription(
            sns_subscriptions.EmailSubscription("alerts@nexora.ai")
        )

    def _create_dashboard(self) -> None:
        """Create CloudWatch dashboard for monitoring."""
        
        self.dashboard = cloudwatch.Dashboard(
            self,
            "NexoraDashboard",
            dashboard_name=f"Nexora-AI-Platform-{self.stage}",
        )

        # API Gateway metrics
        api_widget = cloudwatch.GraphWidget(
            title="API Gateway Metrics",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ApiGateway",
                    metric_name="Count",
                    dimensions_map={
                        "ApiName": self.api_stack.api.rest_api_name,
                        "Stage": self.stage,
                    },
                    statistic="Sum",
                ),
                cloudwatch.Metric(
                    namespace="AWS/ApiGateway",
                    metric_name="4XXError",
                    dimensions_map={
                        "ApiName": self.api_stack.api.rest_api_name,
                        "Stage": self.stage,
                    },
                    statistic="Sum",
                ),
                cloudwatch.Metric(
                    namespace="AWS/ApiGateway",
                    metric_name="5XXError",
                    dimensions_map={
                        "ApiName": self.api_stack.api.rest_api_name,
                        "Stage": self.stage,
                    },
                    statistic="Sum",
                ),
            ],
            right=[
                cloudwatch.Metric(
                    namespace="AWS/ApiGateway",
                    metric_name="Latency",
                    dimensions_map={
                        "ApiName": self.api_stack.api.rest_api_name,
                        "Stage": self.stage,
                    },
                    statistic="Average",
                ),
            ],
        )

        # Lambda function metrics
        lambda_functions = [
            ("Content Generation", self.ai_stack.content_generation_function),
            ("RAG Pipeline", self.ai_stack.rag_pipeline_function),
            ("Automation Controller", self.ai_stack.automation_controller_function),
            ("Publishing", self.ai_stack.publishing_function),
            ("Analytics", self.ai_stack.analytics_function),
            ("Tenant Management", self.ai_stack.tenant_management_function),
            ("Responsible AI", self.ai_stack.responsible_ai_function),
        ]

        for name, function in lambda_functions:
            lambda_widget = cloudwatch.GraphWidget(
                title=f"{name} Lambda Metrics",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Invocations",
                        dimensions_map={
                            "FunctionName": function.function_name,
                        },
                        statistic="Sum",
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Errors",
                        dimensions_map={
                            "FunctionName": function.function_name,
                        },
                        statistic="Sum",
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Throttles",
                        dimensions_map={
                            "FunctionName": function.function_name,
                        },
                        statistic="Sum",
                    ),
                ],
                right=[
                    cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Duration",
                        dimensions_map={
                            "FunctionName": function.function_name,
                        },
                        statistic="Average",
                    ),
                ],
            )
            self.dashboard.add_widgets(lambda_widget)

        # Custom business metrics
        business_widget = cloudwatch.GraphWidget(
            title="Business Metrics",
            left=[
                cloudwatch.Metric(
                    namespace="Nexora/Business",
                    metric_name="ContentGenerated",
                    statistic="Sum",
                ),
                cloudwatch.Metric(
                    namespace="Nexora/Business",
                    metric_name="ContentPublished",
                    statistic="Sum",
                ),
            ],
            right=[
                cloudwatch.Metric(
                    namespace="Nexora/Business",
                    metric_name="ActiveUsers",
                    statistic="Sum",
                ),
            ],
        )

        # Add widgets to dashboard
        self.dashboard.add_widgets(
            api_widget,
            business_widget,
        )

    def _create_alarms(self) -> None:
        """Create CloudWatch alarms for critical metrics."""
        
        # API Gateway error rate alarm
        api_error_alarm = cloudwatch.Alarm(
            self,
            "ApiErrorRateAlarm",
            alarm_name=f"nexora-api-error-rate-{self.stage}",
            alarm_description="API Gateway error rate is too high",
            metric=cloudwatch.Metric(
                namespace="AWS/ApiGateway",
                metric_name="4XXError",
                dimensions_map={
                    "ApiName": self.api_stack.api.rest_api_name,
                    "Stage": self.stage,
                },
                statistic="Sum",
                period=cloudwatch.Duration.minutes(5),
            ),
            threshold=10,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )

        api_error_alarm.add_alarm_action(
            cw_actions.SnsAction(self.alert_topic)
        )

        # Lambda function error alarms
        lambda_functions = [
            ("content-generation", self.ai_stack.content_generation_function),
            ("rag-pipeline", self.ai_stack.rag_pipeline_function),
            ("automation-controller", self.ai_stack.automation_controller_function),
            ("publishing", self.ai_stack.publishing_function),
        ]

        for name, function in lambda_functions:
            error_alarm = cloudwatch.Alarm(
                self,
                f"{name.title().replace('-', '')}ErrorAlarm",
                alarm_name=f"nexora-{name}-errors-{self.stage}",
                alarm_description=f"{name} Lambda function error rate is too high",
                metric=cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Errors",
                    dimensions_map={
                        "FunctionName": function.function_name,
                    },
                    statistic="Sum",
                    period=cloudwatch.Duration.minutes(5),
                ),
                threshold=5,
                evaluation_periods=2,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            )

            error_alarm.add_alarm_action(
                cw_actions.SnsAction(self.alert_topic)
            )

            # Duration alarm for critical functions
            if name in ["content-generation", "rag-pipeline"]:
                duration_alarm = cloudwatch.Alarm(
                    self,
                    f"{name.title().replace('-', '')}DurationAlarm",
                    alarm_name=f"nexora-{name}-duration-{self.stage}",
                    alarm_description=f"{name} Lambda function duration is too high",
                    metric=cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Duration",
                        dimensions_map={
                            "FunctionName": function.function_name,
                        },
                        statistic="Average",
                        period=cloudwatch.Duration.minutes(5),
                    ),
                    threshold=30000,  # 30 seconds
                    evaluation_periods=3,
                    comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                )

                duration_alarm.add_alarm_action(
                    cw_actions.SnsAction(self.alert_topic)
                )