#!/bin/bash

# Test script for Nexora AI Platform

set -e

echo "🧪 Running Nexora AI Platform tests..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest is not installed. Installing..."
    pip install pytest pytest-asyncio pytest-mock hypothesis
fi

# Set test environment variables
export STAGE=test
export USE_LOCALSTACK=true
export LOCALSTACK_ENDPOINT=http://localhost:4566

# Start LocalStack if not running
if ! curl -s http://localhost:4566/health &> /dev/null; then
    echo "🐳 Starting LocalStack for tests..."
    docker-compose up -d localstack redis
    sleep 10
fi

# Run unit tests
echo "🔬 Running unit tests..."
pytest src/tests/unit/ -v --tb=short

# Run integration tests
echo "🔗 Running integration tests..."
pytest src/tests/integration/ -v --tb=short

# Run property-based tests
echo "🎲 Running property-based tests..."
pytest src/tests/property/ -v --tb=short

# Generate coverage report
echo "📊 Generating coverage report..."
pytest src/tests/ --cov=src --cov-report=html --cov-report=term

echo "✅ All tests completed!"
echo "📊 Coverage report available in htmlcov/index.html"