# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Package Management
**IMPORTANT**: Always use `uv` for all Python package management operations in this project.

```bash
# Install dependencies
uv sync

# Add new dependency
uv add package_name

# Add development dependency
uv add --dev package_name

# Remove dependency
uv remove package_name

# Run Python scripts/commands
uv run python script.py
uv run uvicorn app:app --reload --port 8000
```

### Running the Application
```bash
# Quick start (recommended)
./run.sh

# Manual start
cd backend && uv run uvicorn app:app --reload --port 8000
```

### Environment Setup
```bash
# Install dependencies
uv sync

# Required environment variables in .env file:
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### Access Points
- Web Interface: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Architecture Overview

This is a **tool-based RAG (Retrieval-Augmented Generation) system** where Claude AI decides when to search the knowledge base using function calling, rather than always retrieving documents.

### Core Architecture Pattern

**Query Flow**: Frontend → FastAPI → RAG System → AI Generator (with tools) → Vector Search (if needed) → Response

**Key Architectural Decision**: The system uses Anthropic's tool calling where Claude decides whether to search based on query type, rather than always performing retrieval.

### Component Relationships

1. **RAG System (`rag_system.py`)** - Main orchestrator
   - Coordinates between AI Generator, Session Manager, and Search Tools
   - Manages conversation history and tool availability
   - Entry point: `query(query, session_id)` method

2. **AI Generator (`ai_generator.py`)** - Claude API integration
   - Handles tool execution workflow via `_handle_tool_execution()`
   - System prompt instructs Claude on when to use search tools
   - Temperature set to 0 for deterministic responses

3. **Search Tools (`search_tools.py`)** - Tool interface layer
   - `CourseSearchTool` implements Anthropic tool calling interface
   - `ToolManager` handles tool registration and execution
   - Returns formatted results with source tracking

4. **Vector Store (`vector_store.py`)** - ChromaDB interface
   - Separate collections for course metadata and content chunks
   - Uses `sentence-transformers/all-MiniLM-L6-v2` for embeddings
   - Unified `search()` method with course/lesson filtering

5. **Document Processor (`document_processor.py`)** - Content ingestion
   - Parses course documents with lesson structure detection
   - Creates `CourseChunk` objects with metadata for vector storage
   - Configurable chunking: 800 chars with 100 char overlap

6. **Session Manager (`session_manager.py`)** - Conversation state
   - Manages conversation history (default: 2 message pairs)
   - Thread-safe session storage with auto-generated IDs

### Data Models (`models.py`)

- **Course**: Contains title, lessons, and metadata
- **CourseChunk**: Text chunk with course/lesson context for vector storage  
- **Lesson**: Individual lesson with number and title

### Configuration (`config.py`)

Key settings centralized in `Config` dataclass:
- `ANTHROPIC_MODEL`: "claude-sonnet-4-20250514"
- `CHUNK_SIZE`: 800 characters
- `MAX_RESULTS`: 5 search results
- `MAX_HISTORY`: 2 conversation pairs

### Frontend Architecture

**Simple HTML/CSS/JS stack** (`frontend/` directory):
- `script.js`: Handles API communication, markdown rendering, session management
- Event-driven: user input → `sendMessage()` → POST `/api/query` → UI update
- Uses `marked.js` for markdown rendering and collapsible source display

### Document Loading

On startup (`app.py` startup event):
1. Automatically loads all `.txt`, `.pdf`, `.docx` files from `docs/` folder
2. Processes into course structures with lesson detection  
3. Stores in ChromaDB for semantic search
4. Skips already-processed courses to avoid duplicates

### Key Integration Points

- **Frontend-Backend**: Single `/api/query` endpoint with `{query, session_id}` payload
- **RAG-AI**: Tool definitions passed to Claude via `tools` parameter
- **AI-Search**: Tool execution via `tool_manager.execute_tool()`  
- **Search-Vector**: Unified interface through `vector_store.search()`

### Development Notes

- Uses `uv` for Python package management (Python 3.13+ required)
- No test framework currently configured
- ChromaDB data stored in `./backend/chroma_db/`
- API serves frontend static files from root path `/`
- CORS enabled for development with `allow_origins=["*"]`

## Best Practices

### Code Style
- Always use descriptive variable names