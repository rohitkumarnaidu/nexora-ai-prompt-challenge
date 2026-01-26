#!/bin/bash

# Deployment script for Nexora AI Platform

set -e

# Default values
STAGE=${1:-dev}
REGION=${2:-us-east-1}

echo "🚀 Deploying Nexora AI Platform to $STAGE environment in $REGION..."

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI is not configured or credentials are invalid"
    exit 1
fi

echo "✅ AWS credentials verified"

# Set environment variables
export STAGE=$STAGE
export CDK_DEFAULT_REGION=$REGION
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

echo "📋 Deployment configuration:"
echo "  Stage: $STAGE"
echo "  Region: $REGION"
echo "  Account: $CDK_DEFAULT_ACCOUNT"

# Navigate to infrastructure directory
cd infrastructure

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing CDK dependencies..."
    npm install
fi

# Bootstrap CDK if needed
echo "🏗️  Checking CDK bootstrap..."
if ! cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$REGION; then
    echo "❌ CDK bootstrap failed"
    exit 1
fi

# Synthesize CloudFormation templates
echo "🔨 Synthesizing CloudFormation templates..."
cdk synth --all

# Deploy all stacks
echo "🚀 Deploying stacks..."
cdk deploy --all --require-approval never

# Get outputs
echo "📋 Deployment outputs:"
cdk list --long

echo "✅ Deployment completed successfully!"
echo ""
echo "Next steps:"
echo "1. Update your .env file with the deployed resource names"
echo "2. Configure your frontend application with the API Gateway URL"
echo "3. Set up monitoring and alerting"

cd ..