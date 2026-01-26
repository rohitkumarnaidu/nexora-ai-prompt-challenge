#!/usr/bin/env python3
"""
AWS CDK application entry point for Nexora AI Platform.

This file defines the main CDK application and instantiates all the necessary
stacks for the Nexora AI Platform infrastructure.
"""

import os
from aws_cdk import App, Environment, Tags
from stacks.api_stack import ApiStack
from stacks.auth_stack import AuthStack
from stacks.data_stack import DataStack
from stacks.ai_stack import AiStack
from stacks.monitoring_stack import MonitoringStack


def main():
    """Main CDK application entry point."""
    app = App()
    
    # Get environment configuration
    account = os.environ.get("CDK_DEFAULT_ACCOUNT")
    region = os.environ.get("CDK_DEFAULT_REGION", "us-east-1")
    stage = os.environ.get("STAGE", "dev")
    
    env = Environment(account=account, region=region)
    
    # Common tags for all resources
    Tags.of(app).add("Project", "NexoraAI")
    Tags.of(app).add("Stage", stage)
    Tags.of(app).add("ManagedBy", "CDK")
    
    # Data stack - DynamoDB, S3, OpenSearch
    data_stack = DataStack(
        app,
        f"NexoraAI-Data-{stage}",
        env=env,
        stage=stage,
    )
    
    # Authentication stack - Cognito
    auth_stack = AuthStack(
        app,
        f"NexoraAI-Auth-{stage}",
        env=env,
        stage=stage,
    )
    
    # AI stack - Bedrock, Lambda functions for AI services
    ai_stack = AiStack(
        app,
        f"NexoraAI-AI-{stage}",
        env=env,
        stage=stage,
        data_stack=data_stack,
    )
    
    # API stack - API Gateway, Lambda functions
    api_stack = ApiStack(
        app,
        f"NexoraAI-API-{stage}",
        env=env,
        stage=stage,
        auth_stack=auth_stack,
        data_stack=data_stack,
        ai_stack=ai_stack,
    )
    
    # Monitoring stack - CloudWatch, X-Ray
    monitoring_stack = MonitoringStack(
        app,
        f"NexoraAI-Monitoring-{stage}",
        env=env,
        stage=stage,
        api_stack=api_stack,
        ai_stack=ai_stack,
    )
    
    app.synth()


if __name__ == "__main__":
    main()