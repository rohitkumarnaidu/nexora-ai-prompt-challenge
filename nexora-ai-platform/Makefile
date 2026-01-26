# Makefile for Nexora AI Platform

.PHONY: help setup install test lint format clean deploy destroy

# Default target
help:
	@echo "Nexora AI Platform - Available commands:"
	@echo "  setup     - Set up development environment"
	@echo "  install   - Install dependencies"
	@echo "  test      - Run all tests"
	@echo "  lint      - Run linting"
	@echo "  format    - Format code"
	@echo "  clean     - Clean build artifacts"
	@echo "  deploy    - Deploy to AWS"
	@echo "  destroy   - Destroy AWS resources"
	@echo "  dev       - Start development environment"
	@echo "  logs      - View LocalStack logs"

# Development environment setup
setup:
	@echo "Setting up development environment..."
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt
	cd infrastructure && pip install -r requirements.txt
	cp .env.example .env
	@echo "Setup complete! Don't forget to update .env file"

# Install dependencies
install:
	. venv/bin/activate && pip install -r requirements.txt
	cd infrastructure && pip install -r requirements.txt

# Run tests
test:
	. venv/bin/activate && pytest src/tests/ -v

# Run tests with coverage
test-coverage:
	. venv/bin/activate && pytest src/tests/ --cov=src --cov-report=html --cov-report=term

# Run property-based tests only
test-property:
	. venv/bin/activate && pytest src/tests/property/ -v

# Lint code
lint:
	. venv/bin/activate && flake8 src/
	. venv/bin/activate && mypy src/

# Format code
format:
	. venv/bin/activate && black src/
	. venv/bin/activate && isort src/

# Clean build artifacts
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/

# Start development environment
dev:
	docker-compose up -d
	@echo "Development environment started!"
	@echo "LocalStack: http://localhost:4566"
	@echo "Redis: localhost:6379"

# Stop development environment
dev-stop:
	docker-compose down

# View LocalStack logs
logs:
	docker-compose logs -f localstack

# Deploy to AWS (development)
deploy-dev:
	cd infrastructure && cdk deploy --all --profile dev

# Deploy to AWS (production)
deploy-prod:
	cd infrastructure && STAGE=prod cdk deploy --all --profile prod

# Destroy AWS resources (development)
destroy-dev:
	cd infrastructure && cdk destroy --all --profile dev

# Destroy AWS resources (production)
destroy-prod:
	cd infrastructure && STAGE=prod cdk destroy --all --profile prod

# Bootstrap CDK
bootstrap:
	cd infrastructure && cdk bootstrap

# Synthesize CloudFormation templates
synth:
	cd infrastructure && cdk synth --all

# Validate CDK code
validate:
	cd infrastructure && cdk synth --all > /dev/null

# Install pre-commit hooks
pre-commit:
	. venv/bin/activate && pre-commit install

# Run pre-commit on all files
pre-commit-all:
	. venv/bin/activate && pre-commit run --all-files

# Create migration
migrate:
	@echo "Database migrations not implemented yet"

# Seed test data
seed:
	@echo "Test data seeding not implemented yet"

# Generate API documentation
docs:
	@echo "API documentation generation not implemented yet"

# Security scan
security:
	. venv/bin/activate && bandit -r src/

# Dependency check
deps-check:
	. venv/bin/activate && pip-audit

# Update dependencies
deps-update:
	. venv/bin/activate && pip-compile --upgrade requirements.in
	cd infrastructure && npm update