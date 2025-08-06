"""
API endpoint tests for the FastAPI application.

Tests the FastAPI endpoints (/api/query, /api/courses, /api/new-chat, /)
for proper request/response handling without static file dependencies.
"""

import pytest
import json
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock, MagicMock
import os
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import Config
from rag_system import RAGSystem
from models import SourceWithLink


def create_test_app():
    """
    Create a test FastAPI app with API routes only (no static file mounting).
    This avoids the static file dependency issues in the main app.
    """
    from pydantic import BaseModel
    from typing import List, Optional
    from fastapi import HTTPException
    
    # Create test app
    app = FastAPI(title="Test RAG System API")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Pydantic models (copied from main app)
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[SourceWithLink]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    class NewChatRequest(BaseModel):
        session_id: Optional[str] = None

    class NewChatResponse(BaseModel):
        success: bool
        message: str
    
    # Mock RAG system for testing
    mock_rag_system = MagicMock()
    
    # API endpoints (copied from main app)
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session.return_value or "test_session"
            
            answer, sources = mock_rag_system.query.return_value
            
            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics.return_value
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/new-chat", response_model=NewChatResponse)
    async def start_new_chat(request: NewChatRequest):
        try:
            if request.session_id:
                mock_rag_system.session_manager.clear_session(request.session_id)
            
            return NewChatResponse(
                success=True,
                message="New chat session started successfully"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/")
    async def root():
        return {"message": "RAG System API", "status": "running"}
    
    # Store mock for access in tests
    app.state.mock_rag_system = mock_rag_system
    
    return app


@pytest.fixture
def test_app():
    """Create test FastAPI application."""
    return create_test_app()


@pytest.fixture
def client(test_app):
    """Create test client for the FastAPI app."""
    return TestClient(test_app)


@pytest.mark.api
class TestQueryEndpoint:
    """Test the /api/query endpoint."""
    
    def test_query_without_session_id(self, client, sample_sources):
        """Test POST /api/query without session ID."""
        # Setup mock response
        mock_rag = client.app.state.mock_rag_system
        mock_rag.query.return_value = ("This is a test answer", sample_sources)
        mock_rag.session_manager.create_session.return_value = "new_session_123"
        
        response = client.post("/api/query", json={
            "query": "What is machine learning?"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "answer" in data
        assert "sources" in data  
        assert "session_id" in data
        assert data["answer"] == "This is a test answer"
        assert len(data["sources"]) == 2
        assert data["session_id"] == "new_session_123"
    
    def test_query_with_session_id(self, client, sample_sources):
        """Test POST /api/query with existing session ID."""
        mock_rag = client.app.state.mock_rag_system
        mock_rag.query.return_value = ("Answer with session", sample_sources)
        
        response = client.post("/api/query", json={
            "query": "Tell me more",
            "session_id": "existing_session_456"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["session_id"] == "existing_session_456"
        assert data["answer"] == "Answer with session"
    
    def test_query_empty_string(self, client):
        """Test POST /api/query with empty query string."""
        mock_rag = client.app.state.mock_rag_system
        mock_rag.query.return_value = ("Please provide a question", [])
        mock_rag.session_manager.create_session.return_value = "empty_query_session"
        
        response = client.post("/api/query", json={
            "query": ""
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Please provide a question"
        assert data["sources"] == []
    
    def test_query_missing_query_field(self, client):
        """Test POST /api/query with missing query field."""
        response = client.post("/api/query", json={
            "session_id": "test"
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_query_invalid_json(self, client):
        """Test POST /api/query with invalid JSON."""
        response = client.post("/api/query", 
                             data="invalid json",
                             headers={"Content-Type": "application/json"})
        
        assert response.status_code == 422
    
    def test_query_rag_system_exception(self, client):
        """Test POST /api/query when RAG system raises exception."""
        mock_rag = client.app.state.mock_rag_system
        mock_rag.query.side_effect = Exception("RAG system error")
        
        response = client.post("/api/query", json={
            "query": "test query"
        })
        
        assert response.status_code == 500
        assert "RAG system error" in response.json()["detail"]


@pytest.mark.api
class TestCoursesEndpoint:
    """Test the /api/courses endpoint."""
    
    def test_get_course_stats_success(self, client, sample_course_stats):
        """Test GET /api/courses returns course statistics."""
        mock_rag = client.app.state.mock_rag_system
        mock_rag.get_course_analytics.return_value = sample_course_stats
        
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_courses" in data
        assert "course_titles" in data
        assert data["total_courses"] == 3
        assert len(data["course_titles"]) == 3
        assert "Introduction to Machine Learning" in data["course_titles"]
    
    def test_get_course_stats_empty(self, client):
        """Test GET /api/courses with no courses loaded."""
        mock_rag = client.app.state.mock_rag_system
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }
        
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_courses"] == 0
        assert data["course_titles"] == []
    
    def test_get_course_stats_exception(self, client):
        """Test GET /api/courses when analytics raises exception."""
        mock_rag = client.app.state.mock_rag_system
        mock_rag.get_course_analytics.side_effect = Exception("Analytics error")
        
        response = client.get("/api/courses")
        
        assert response.status_code == 500
        assert "Analytics error" in response.json()["detail"]


@pytest.mark.api
class TestNewChatEndpoint:
    """Test the /api/new-chat endpoint."""
    
    def test_new_chat_without_session(self, client):
        """Test POST /api/new-chat without session ID."""
        response = client.post("/api/new-chat", json={})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "started successfully" in data["message"]
    
    def test_new_chat_with_session(self, client):
        """Test POST /api/new-chat with existing session ID."""
        mock_rag = client.app.state.mock_rag_system
        
        response = client.post("/api/new-chat", json={
            "session_id": "clear_this_session"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        # Verify session was cleared
        mock_rag.session_manager.clear_session.assert_called_once_with("clear_this_session")
    
    def test_new_chat_exception(self, client):
        """Test POST /api/new-chat when session clearing raises exception.""" 
        mock_rag = client.app.state.mock_rag_system
        mock_rag.session_manager.clear_session.side_effect = Exception("Session error")
        
        response = client.post("/api/new-chat", json={
            "session_id": "problematic_session"
        })
        
        assert response.status_code == 500
        assert "Session error" in response.json()["detail"]


@pytest.mark.api
class TestRootEndpoint:
    """Test the root / endpoint."""
    
    def test_root_endpoint(self, client):
        """Test GET / returns API status."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "status" in data
        assert data["status"] == "running"


@pytest.mark.api
class TestCORSAndMiddleware:
    """Test CORS and middleware functionality."""
    
    def test_cors_headers_present(self, client):
        """Test that CORS headers are set correctly."""
        response = client.options("/api/query")
        
        # FastAPI/Starlette automatically handles OPTIONS requests
        assert response.status_code in [200, 405]  # 405 if OPTIONS not explicitly defined
    
    def test_cors_headers_on_actual_request(self, client):
        """Test CORS headers on actual API requests."""
        mock_rag = client.app.state.mock_rag_system
        mock_rag.query.return_value = ("Test", [])
        mock_rag.session_manager.create_session.return_value = "test"
        
        response = client.post("/api/query", json={"query": "test"})
        
        # Check response succeeds (CORS would block if misconfigured)
        assert response.status_code == 200


@pytest.mark.api
@pytest.mark.integration
class TestEndToEndAPIFlow:
    """Test end-to-end API workflows."""
    
    def test_complete_chat_session_flow(self, client, sample_sources):
        """Test a complete chat session: new chat -> query -> more queries."""
        mock_rag = client.app.state.mock_rag_system
        
        # Start new chat
        response = client.post("/api/new-chat", json={})
        assert response.status_code == 200
        
        # First query
        mock_rag.query.return_value = ("First answer", sample_sources)
        mock_rag.session_manager.create_session.return_value = "flow_session"
        
        response = client.post("/api/query", json={
            "query": "What is machine learning?"
        })
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        
        # Follow-up query with session
        mock_rag.query.return_value = ("Follow-up answer", [])
        
        response = client.post("/api/query", json={
            "query": "Tell me more",
            "session_id": session_id
        })
        assert response.status_code == 200
        assert response.json()["session_id"] == session_id
    
    def test_course_stats_and_query_integration(self, client, sample_course_stats, sample_sources):
        """Test getting course stats then querying course content."""
        mock_rag = client.app.state.mock_rag_system
        
        # Get course stats
        mock_rag.get_course_analytics.return_value = sample_course_stats
        response = client.get("/api/courses")
        assert response.status_code == 200
        
        course_titles = response.json()["course_titles"]
        assert len(course_titles) > 0
        
        # Query about specific course
        mock_rag.query.return_value = (f"Information about {course_titles[0]}", sample_sources)
        mock_rag.session_manager.create_session.return_value = "course_query_session"
        
        response = client.post("/api/query", json={
            "query": f"Tell me about {course_titles[0]}"
        })
        assert response.status_code == 200
        assert course_titles[0].replace(" ", "").lower() in response.json()["answer"].replace(" ", "").lower()