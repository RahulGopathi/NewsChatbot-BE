# News Chatbot Backend

A RAG-powered chatbot backend for answering queries about news articles using FastAPI, Redis, and Gemini AI.

![GitHub Actions Status](https://github.com/RahulGopathi/NewsChatbot-BE/workflows/Build%20and%20Push%20Docker%20Image/badge.svg)

## Features

- RAG (Retrieval-Augmented Generation) pipeline for accurate news-based responses
- Session-based chat history using Redis
- Vector store (Qdrant) for efficient document retrieval
- RESTful API endpoints for chat interaction
- News article ingestion from multiple RSS feeds
- Article categorization using RSS metadata
- Sophisticated query analysis system to understand user intent

## Tech Stack

- **FastAPI**: High-performance web framework
- **Redis**: Session management and caching
- **Qdrant**: Vector database for semantic search
- **Gemini AI**: LLM for response generation
- **Jina AI**: Embeddings for semantic search
- **Docker**: Containerization
- **Poetry**: Dependency management

## Prerequisites

- Python 3.8+
- Redis server
- Qdrant vector store
- Gemini API key
- Jina AI API key (for embeddings)

## Local Setup

1. Clone the repository:

```bash
git clone https://github.com/RahulGopathi/NewsChatbot-BE.git
cd NewsChatbot-BE
```

2. Set up Python environment with Poetry:

```bash
# Install Poetry if you don't have it
pip install poetry

# Install dependencies
poetry install

# Activate the virtual environment
poetry shell
```

3. Configure environment variables:

Create a `.env` file in the root directory with:

```
# API Keys
GEMINI_API_KEY=your-gemini-api-key
JINA_API_KEY=your-jina-api-key

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Qdrant Configuration
VECTOR_STORE_HOST=localhost
VECTOR_STORE_PORT=6333
```

## Running the Application

### Option 1: Using Docker Compose (Recommended)

This application is fully containerized with all dependencies:

```bash
# Start all services including Redis, Qdrant, and API
docker-compose up -d
```

The frontend will be available at `https://localhost` and the API will be available at `http://localhost:8000`

For development, you can run only the dependencies and the API separately:

```bash
# Start only Redis and Qdrant
docker-compose up -d redis qdrant

# Run the API with auto-reload
python run.py
```

### Option 2: Manual Setup

1. Start Redis server:

```bash
redis-server
```

2. Start Qdrant vector store:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

3. Run the FastAPI application:

```bash
python run.py
# or
uvicorn main:app --reload
```

## News Ingestion

The application includes a script to ingest news articles from RSS feeds:

```bash
python news_ingestion.py --limit 100
```

By default, it will ingest articles from:

- New York Times Homepage
- New York Times Technology section

Articles are stored in the `data/raw_articles` directory with metadata and categorization.

## Project Structure

```
NewsChatbot-BE/
├── app/                     # Application code
│   ├── api/                 # API endpoints
│   │   └── chat.py          # Chat-related endpoints
│   ├── core/                # Core settings and config
│   ├── models/              # Pydantic models
│   ├── rag/                 # Retrieval-Augmented Generation
│   │   ├── embeddings.py    # Embedding generation
│   │   ├── query_analyzer.py # Query analysis
│   │   └── vector_store.py  # Vector database interaction
│   ├── services/            # Business logic
│   └── utils/               # Utility functions
├── data/                    # Data storage
│   └── raw_articles/        # Ingested news articles
├── logs/                    # Application logs
├── env/                     # Environment configurations
├── Dockerfile               # Docker configuration
├── docker-compose.yml       # Docker Compose configuration
├── pyproject.toml           # Poetry dependencies
├── main.py                  # FastAPI application
├── run.py                   # Application runner
└── news_ingestion.py        # News ingestion script
```

## API Endpoints

### Chat Endpoints

- `POST /api/v1/chat/query`: Send a message and get a response

  ```json
  {
    "message": "Tell me about recent tech news",
    "session_id": "user_session_123"
  }
  ```

- `GET /api/v1/chat/history/{session_id}`: Get chat history for a session
- `DELETE /api/v1/chat/clear/{session_id}`: Clear a chat session

### Health Check

- `GET /health`: Check API health status

## Redis Session Management and TTL Configuration

The application uses Redis for chat session management with careful attention to TTL (Time-To-Live) configuration:

### TTL Implementation

Chat sessions in Redis are configured with a 24-hour expiration (86400 seconds) as seen in the `chat_service.py` file:

```python
# Set with expiration of 1 day (86400 seconds)
self.redis_client.set(session_key, json.dumps(session_data), ex=86400)
```

This ensures that:

- Sessions are automatically cleaned up after 24 hours of inactivity
- Server resources are conserved by not storing inactive sessions indefinitely
- User privacy is protected by removing old conversation data

### Redis Configuration

Redis is configured in `docker-compose.yml` with data persistence enabled:

```yaml
redis:
  image: redis:latest
  command: redis-server --appendonly yes
  # ...other settings
```

The AOF (Append-Only File) persistence ensures that session data survives container restarts but still respects the TTL settings.

### Session Keys

Sessions are stored with a namespace prefix for easy identification:

```
chat:session:{session_id}
```

## Deployment

### Docker Setup

The application includes a Dockerfile and Docker Compose configuration for easy deployment:

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build and run manually
docker build -t newschatbot-be .
docker run -p 8000:8000 --env-file .env newschatbot-be
```

### GitHub Container Registry

After pushing a tag to GitHub, the GitHub Actions workflow will automatically build and publish the Docker image:

```bash
docker pull ghcr.io/rahulgopathi/newschatbot-be:latest
docker run -p 8000:8000 --env-file .env ghcr.io/rahulgopathi/newschatbot-be:latest
```

## License

MIT License
