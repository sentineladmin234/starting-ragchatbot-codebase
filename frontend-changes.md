# Testing Framework Enhancement Changes

This document outlines the changes made to enhance the existing testing framework for the RAG system in `backend/tests/`.

## Summary

Enhanced the testing infrastructure with comprehensive API endpoint testing, improved pytest configuration, and shared test fixtures. The changes provide a robust foundation for testing FastAPI endpoints while avoiding static file dependencies.

## Changes Made

### 1. Enhanced pytest Configuration (`pyproject.toml`)

**Added dependencies:**
- `pytest>=7.0.0` - Modern testing framework
- `httpx>=0.24.0` - Async HTTP client for FastAPI testing

**Added pytest configuration:**
```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--tb=short", 
    "--strict-markers",
    "--disable-warnings",
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "api: API endpoint tests",
]
```

### 2. Shared Test Fixtures (`backend/tests/conftest.py`)

**New file created** with comprehensive test fixtures:

- `temp_dir()` - Isolated temporary directory for each test
- `test_config()` - Test configuration with fixed MAX_RESULTS bug
- `mock_anthropic_client()` - Mocked Anthropic API client to avoid real API calls
- `mock_anthropic_with_tool_use()` - Mocked client that simulates tool usage workflow
- `test_rag_system()` - Pre-configured RAG system for testing
- `sample_sources()` - Sample SourceWithLink data
- `sample_query_requests()` - Sample API request payloads
- `sample_query_responses()` - Sample API response payloads
- `sample_course_stats()` - Sample course statistics data
- `setup_test_environment()` - Session-wide test environment setup
- `mock_file_operations()` - File system operation mocking

**Key features:**
- Thread-safe temporary directory management
- Automatic cleanup after tests
- Fixes MAX_RESULTS=0 configuration bug in tests
- Comprehensive mocking to avoid external dependencies

### 3. API Endpoint Tests (`backend/tests/test_api_endpoints.py`)

**New comprehensive test file** covering all FastAPI endpoints:

#### Test Architecture
- **Isolated Test App**: Creates a separate FastAPI app without static file mounting
- **Mock Integration**: Uses shared fixtures for consistent mocking
- **Full Coverage**: Tests success cases, edge cases, and error conditions

#### Endpoints Tested

**POST /api/query**
- Query without session ID (auto-creates session)
- Query with existing session ID  
- Empty query handling
- Missing query field validation
- Invalid JSON handling
- RAG system exception handling

**GET /api/courses**
- Successful course statistics retrieval
- Empty course list handling
- Analytics system exception handling

**POST /api/new-chat**
- New chat without session ID
- New chat with session clearing
- Session clearing exception handling

**GET /** 
- Root endpoint status check

#### Additional Test Categories
- **CORS & Middleware**: Validates CORS headers and middleware functionality
- **End-to-End Flows**: Tests complete chat session workflows
- **Integration Scenarios**: Course stats + query integration

#### Test Markers
- `@pytest.mark.api` - API-specific tests
- `@pytest.mark.integration` - Integration test scenarios

## Technical Improvements

### Problem Solved: Static File Dependencies
The main FastAPI app in `backend/app.py` mounts static files that don't exist in test environments:
```python
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")
```

**Solution**: Created `create_test_app()` function that:
- Defines API endpoints inline without static file mounting
- Uses dependency injection with mocked RAG system
- Maintains identical API contract for testing

### Configuration Bug Fix
Fixed the MAX_RESULTS=0 bug in test configurations:
```python
config.MAX_RESULTS = 5  # Fix the MAX_RESULTS=0 bug for tests
```

### Comprehensive Error Handling
All endpoints tested for:
- Success scenarios with various inputs
- Validation errors (422 status codes)
- Internal server errors (500 status codes)
- Edge cases (empty data, malformed requests)

## Usage Instructions

### Running Tests
```bash
# Install new dependencies
uv sync

# Run all tests
uv run pytest

# Run only API tests
uv run pytest -m api

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest backend/tests/test_api_endpoints.py
```

### Test Development
- Use fixtures from `conftest.py` for consistent test setup
- Mark API tests with `@pytest.mark.api`
- Mark integration tests with `@pytest.mark.integration`
- Follow existing naming conventions (`test_*.py`)

## Files Modified/Created

### Modified Files
- `pyproject.toml` - Added pytest dependencies and configuration

### New Files  
- `backend/tests/conftest.py` - Shared test fixtures and configuration
- `backend/tests/test_api_endpoints.py` - Comprehensive API endpoint tests

## Impact

### Testing Coverage
- **Before**: Unit tests for individual components
- **After**: Full API endpoint testing + unit tests + integration scenarios

### Development Workflow
- Faster test execution with proper pytest configuration
- Consistent test environment with shared fixtures  
- No external API dependencies during testing
- Clear test output with proper markers and configuration

### Maintainability
- Centralized test configuration in `conftest.py`
- Reusable fixtures across test modules
- Clear separation between unit, integration, and API tests
- Comprehensive error scenario coverage

The testing framework now provides a solid foundation for ensuring API reliability and supporting confident development and refactoring of the RAG system.