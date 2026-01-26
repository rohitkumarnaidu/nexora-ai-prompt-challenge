# Nexora AI Platform - Development Setup

## Quick Start (Windows)

### Option 1: Automated Setup
1. Double-click `start-dev.bat` to automatically start both frontend and backend
2. The script will install dependencies and open the application in your browser

### Option 2: Manual Setup

#### Backend Setup
```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate.bat

# Install Python dependencies
pip install fastapi uvicorn pydantic python-multipart

# Start the development API server
python src/dev_server.py
```
The backend will be available at: http://localhost:8001
API documentation: http://localhost:8001/docs

#### Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install Node.js dependencies
npm install

# Start the development server
npm run dev
```
The frontend will be available at: http://localhost:3000

## What You'll See

### Frontend Features (Demo Mode)
- **Dashboard**: Overview with mock statistics
- **Content Generation**: AI-powered content creation interface
- **Workflows**: Automation management (placeholder)
- **Analytics**: Performance metrics (placeholder)
- **Settings**: Platform configuration (placeholder)

### Backend Features (Mock API)
- **Authentication**: Mock JWT-based auth
- **Content Generation**: Simulated AI content creation
- **Multi-tenant**: Tenant isolation (mocked)
- **Analytics**: Dashboard metrics
- **Health Checks**: Service status monitoring

## Development Notes

### Current Implementation Status
- ✅ Frontend UI with React/Next.js and Tailwind CSS
- ✅ Backend API with FastAPI running in virtual environment
- ✅ Mock authentication system
- ✅ Content generation interface
- ✅ TypeScript configuration fixed
- ⏳ AWS integration (requires LocalStack or real AWS)
- ⏳ Real AI models (requires Amazon Bedrock)
- ⏳ Vector database (requires OpenSearch)

### Mock vs Real Features
This development setup uses mock data and simulated responses to demonstrate the UI and API structure. The full implementation includes:

- **Real AI**: Amazon Bedrock integration for content generation
- **RAG Pipeline**: OpenSearch vector database for context retrieval
- **AWS Services**: Lambda, API Gateway, DynamoDB, S3
- **Authentication**: AWS Cognito integration
- **Multi-tenant**: Real tenant isolation and resource quotas

### Next Steps
1. **View the Application**: Use the development servers to explore the UI
2. **Review the Code**: Examine the frontend and backend implementation
3. **Run Tests**: Execute the test suite with `pytest src/tests/`
4. **Deploy to AWS**: Use the CDK infrastructure for cloud deployment

## Troubleshooting

### Common Issues
- **Port conflicts**: Backend now runs on port 8001, frontend on 3000
- **Node.js not found**: Install Node.js 18+ from nodejs.org
- **Python dependencies**: Make sure you have Python 3.9+ installed
- **Virtual environment**: Ensure venv is activated before running backend
- **Permission errors**: Run as administrator if needed

### Getting Help
- Check the main README.md for full documentation
- Review the task list in `.kiro/specs/nexora-ai-platform/tasks.md`
- Examine the requirements and design documents in `.kiro/specs/`