#!/usr/bin/env python3
"""
Development server for Nexora AI Platform
Provides a simple FastAPI server for local development without AWS dependencies
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
import json
import time
from datetime import datetime, timedelta

app = FastAPI(
    title="Nexora AI Platform API",
    description="AI-powered content automation platform",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# Mock data
mock_users = {
    "demo@nexora.ai": {
        "id": "user-123",
        "email": "demo@nexora.ai",
        "name": "Demo User",
        "role": "CREATOR",
        "tenant_id": "tenant-123"
    }
}

mock_content = []

# Pydantic models
class ContentRequest(BaseModel):
    prompt: str
    content_type: str = "article"
    automation_mode: str = "partial"

class ContentResponse(BaseModel):
    id: str
    content: str
    status: str
    created_at: str
    prompt: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    tenant_id: str

# Auth dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    # In development, return mock user
    return mock_users["demo@nexora.ai"]

@app.get("/")
async def root():
    return {
        "message": "Nexora AI Platform API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "api": "running",
            "auth": "mock",
            "ai": "mock",
            "database": "mock"
        }
    }

@app.post("/auth/login")
async def login(email: str, password: str):
    # Mock authentication
    if email in mock_users:
        user = mock_users[email]
        return {
            "access_token": f"mock-jwt-token-{user['id']}",
            "token_type": "bearer",
            "user": user
        }
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(user: dict = Depends(get_current_user)):
    return user

@app.post("/content/generate", response_model=ContentResponse)
async def generate_content(
    request: ContentRequest,
    user: dict = Depends(get_current_user)
):
    # Simulate AI content generation
    content_id = f"content-{len(mock_content) + 1}"
    
    # Mock content generation based on prompt
    generated_content = f"""# Generated Content

Based on your prompt: "{request.prompt}"

## Introduction
This is AI-generated content created by the Nexora AI Platform. In the full implementation, this would be powered by:

- **Amazon Bedrock** for advanced language models
- **LangChain** for orchestration and prompt engineering  
- **RAG Pipeline** for context-aware generation using your knowledge base
- **OpenSearch** for semantic search and retrieval

## Key Features Demonstrated

1. **Content Generation**: AI-powered content creation
2. **Human Review**: Content pending review in {request.automation_mode} mode
3. **Multi-Platform Publishing**: Ready for distribution
4. **Analytics Integration**: Performance tracking enabled

## Next Steps

This content is now in your review queue. You can:
- Edit and refine the content
- Approve for publishing
- Schedule for later publication
- Add to your content library

---
*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} by Nexora AI Platform*
"""

    content_item = {
        "id": content_id,
        "content": generated_content,
        "status": "pending_review" if request.automation_mode != "full" else "approved",
        "created_at": datetime.now().isoformat(),
        "prompt": request.prompt,
        "user_id": user["id"],
        "tenant_id": user["tenant_id"]
    }
    
    mock_content.append(content_item)
    
    return content_item

@app.get("/content", response_model=List[ContentResponse])
async def list_content(user: dict = Depends(get_current_user)):
    # Filter content by user's tenant
    user_content = [
        item for item in mock_content 
        if item.get("tenant_id") == user["tenant_id"]
    ]
    return user_content

@app.get("/content/{content_id}", response_model=ContentResponse)
async def get_content(content_id: str, user: dict = Depends(get_current_user)):
    content_item = next(
        (item for item in mock_content if item["id"] == content_id),
        None
    )
    if not content_item:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Check tenant access
    if content_item.get("tenant_id") != user["tenant_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return content_item

@app.get("/analytics/dashboard")
async def get_dashboard_analytics(user: dict = Depends(get_current_user)):
    return {
        "content_generated": len(mock_content),
        "active_workflows": 3,
        "team_members": 8,
        "success_rate": "94%",
        "recent_activity": [
            {
                "type": "content_generated",
                "title": "Blog post about AI trends",
                "timestamp": (datetime.now() - timedelta(hours=2)).isoformat()
            },
            {
                "type": "content_published",
                "title": "Social media campaign",
                "timestamp": (datetime.now() - timedelta(hours=5)).isoformat()
            },
            {
                "type": "workflow_completed",
                "title": "Weekly newsletter",
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat()
            }
        ]
    }

if __name__ == "__main__":
    print("🚀 Starting Nexora AI Platform Development Server")
    print("📍 API Documentation: http://localhost:8001/docs")
    print("🌐 Frontend: http://localhost:3000")
    print("💡 This is a development server with mock data")
    
    uvicorn.run(
        "dev_server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )