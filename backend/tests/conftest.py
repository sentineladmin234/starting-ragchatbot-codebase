"""
Shared test fixtures and configuration for the test suite.

This file provides common fixtures for mocking and test data setup
that can be used across multiple test modules.
"""

import os
import sys
import tempfile
import shutil
import pytest
from unittest.mock import Mock, patch
from typing import Generator

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import Config
from rag_system import RAGSystem
from models import SourceWithLink


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for test isolation."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@pytest.fixture
def test_config(temp_dir: str) -> Config:
    """Create a test configuration with isolated storage."""
    config = Config()
    config.MAX_RESULTS = 5  # Fix the MAX_RESULTS=0 bug for tests
    config.CHROMA_PATH = os.path.join(temp_dir, "test_chroma")
    config.CHUNK_SIZE = 500  # Smaller chunks for faster tests
    config.MAX_HISTORY = 2
    return config


@pytest.fixture
def mock_anthropic_client():
    """Create a mocked Anthropic client to avoid API calls during tests."""
    with patch('anthropic.Anthropic') as mock_anthropic_class:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="This is a test response from Claude.")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_anthropic_with_tool_use():
    """Create a mocked Anthropic client that simulates tool usage."""
    with patch('anthropic.Anthropic') as mock_anthropic_class:
        mock_client = Mock()
        
        # Mock tool use response
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.id = "tool_test_123"
        mock_tool_block.input = {"query": "test query", "course": None, "lesson": None}
        
        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block]
        mock_initial_response.stop_reason = "tool_use"
        
        # Mock final response after tool execution
        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Based on the course content, here's what I found...")]
        mock_final_response.stop_reason = "end_turn"
        
        mock_client.messages.create.side_effect = [mock_initial_response, mock_final_response]
        mock_anthropic_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def test_rag_system(test_config: Config, mock_anthropic_client) -> RAGSystem:
    """Create a RAG system instance for testing with mocked AI."""
    return RAGSystem(test_config)


@pytest.fixture
def sample_sources() -> list[SourceWithLink]:
    """Create sample source data for testing."""
    return [
        SourceWithLink(
            course="Introduction to Machine Learning",
            lesson="Lesson 1: What is ML?",
            text="Machine learning is a subset of artificial intelligence...",
            link="#course-intro-ml-lesson-1"
        ),
        SourceWithLink(
            course="Deep Learning Fundamentals", 
            lesson="Lesson 2: Neural Networks",
            text="Neural networks are computational models inspired by the brain...",
            link="#course-deep-learning-lesson-2"
        )
    ]


@pytest.fixture
def sample_query_requests():
    """Sample API request payloads for testing."""
    return {
        "basic_query": {
            "query": "What is machine learning?",
            "session_id": None
        },
        "query_with_session": {
            "query": "Tell me more about neural networks", 
            "session_id": "test_session_123"
        },
        "empty_query": {
            "query": "",
            "session_id": None
        }
    }


@pytest.fixture
def sample_query_responses():
    """Sample API response payloads for testing.""" 
    return {
        "successful_response": {
            "answer": "Machine learning is a subset of AI that enables computers to learn from data.",
            "sources": [
                {
                    "course": "ML Basics",
                    "lesson": "Introduction", 
                    "text": "Sample content",
                    "link": "#test-link"
                }
            ],
            "session_id": "test_session_123"
        },
        "empty_response": {
            "answer": "I don't have information about that topic.",
            "sources": [],
            "session_id": "test_session_456"
        }
    }


@pytest.fixture
def sample_course_stats():
    """Sample course statistics for testing."""
    return {
        "total_courses": 3,
        "course_titles": [
            "Introduction to Machine Learning",
            "Deep Learning Fundamentals", 
            "Natural Language Processing"
        ]
    }


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up the test environment before all tests run."""
    # Suppress warnings during tests
    import warnings
    warnings.filterwarnings("ignore", message="resource_tracker: There appear to be.*")
    
    # Set test environment variable
    os.environ["TESTING"] = "true"
    
    yield
    
    # Cleanup after all tests
    if "TESTING" in os.environ:
        del os.environ["TESTING"]


@pytest.fixture
def mock_file_operations():
    """Mock file operations to avoid filesystem dependencies in tests."""
    with patch('os.path.exists', return_value=True), \
         patch('os.listdir', return_value=['test_course.txt']), \
         patch('builtins.open', create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = "Test course content"
        yield mock_open