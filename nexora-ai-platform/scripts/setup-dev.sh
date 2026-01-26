#!/bin/bash

# Development environment setup script for Nexora AI Platform

set -e

echo "🚀 Setting up Nexora AI Platform development environment..."

# Check if Python 3.9+ is installed
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.9+ is required. Current version: $python_version"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# Check if Node.js is installed (for CDK)
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required for AWS CDK"
    exit 1
fi

echo "✅ Node.js found: $(node --version)"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is required for LocalStack"
    exit 1
fi

echo "✅ Docker found: $(docker --version)"

# Create virtual environment
echo "📦 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install CDK dependencies
echo "📦 Installing CDK dependencies..."
cd infrastructure
npm install -g aws-cdk
pip install -r requirements.txt
cd ..

# Copy environment file
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please update .env file with your configuration"
fi

# Start LocalStack
echo "🐳 Starting LocalStack..."
docker-compose up -d localstack redis

# Wait for LocalStack to be ready
echo "⏳ Waiting for LocalStack to be ready..."
sleep 10

# Check LocalStack health
if curl -s http://localhost:4566/health | grep -q "running"; then
    echo "✅ LocalStack is running"
else
    echo "❌ LocalStack failed to start"
    exit 1
fi

# Bootstrap CDK (for LocalStack)
echo "🏗️  Bootstrapping CDK for LocalStack..."
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export CDK_DEFAULT_ACCOUNT=000000000000

cd infrastructure
cdk bootstrap --app "python app.py" aws://000000000000/us-east-1
cd ..

echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Update .env file with your configuration"
echo "2. Run 'source venv/bin/activate' to activate the virtual environment"
echo "3. Run 'cd infrastructure && cdk deploy --all' to deploy the infrastructure"
echo "4. Run tests with 'pytest src/tests/'"
echo ""
echo "LocalStack Dashboard: http://localhost:4566"
echo "Redis: localhost:6379"