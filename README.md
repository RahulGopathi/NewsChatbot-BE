# News Chatbot Backend

A RAG-powered chatbot backend for answering queries about news articles using FastAPI, Redis, and Gemini AI.

## Features

- RAG (Retrieval-Augmented Generation) pipeline for accurate responses
- Session-based chat history using Redis
- Vector store for efficient document retrieval
- RESTful API endpoints for chat interaction
- News article ingestion from multiple RSS feeds (NYT Homepage, Technology)
- Article categorization using RSS metadata

## Prerequisites

- Python 3.8+
- Redis server
- Qdrant vector store
- Gemini API key

## Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd NewsChatbot-BE
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Copy the environment file and update the variables:

```bash
cp .env.example .env
```

5. Update the `.env` file with your configuration:

- Set your Gemini API key
- Configure Redis connection details
- Configure Qdrant vector store settings

## Running the Application

### Option 1: Using Docker Compose

Start both Redis and Qdrant using Docker Compose:

```bash
docker-compose up -d
```

Then run the FastAPI application:

```bash
uvicorn main:app --reload
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
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## News Ingestion

The application includes a service to ingest news articles from multiple RSS feeds:

1. Run the news ingestion script:

```bash
python news_ingestion.py
```

By default, it will ingest around 50 articles. You can adjust this limit:

```bash
python news_ingestion.py --limit 100
```

The service fetches articles from:

- New York Times Homepage
- New York Times Technology section

Articles are stored as JSON files in the `data/raw_articles` directory with their associated categories and metadata. These articles are later used by the RAG pipeline to answer user queries, with categories providing additional context for more accurate responses.

For more details, see [News Ingestion Documentation](docs/news_ingestion.md).

## API Endpoints

### Chat Endpoints

- `POST /api/v1/chat/chat`: Send a message and get a response
- `GET /api/v1/chat/history/{session_id}`: Get chat history for a session
- `DELETE /api/v1/chat/session/{session_id}`: Clear a chat session

### Health Check

- `GET /health`: Check API health status

## Caching Configuration

The application uses Redis for caching chat sessions with the following configuration:

- Session TTL: 24 hours (configurable in Redis)
- Cache warming: Not implemented by default, but can be added by pre-loading common queries

## Development

To add new features or modify existing ones:

1. Create a new branch
2. Make your changes
3. Add tests if necessary
4. Submit a pull request

## License

MIT License
