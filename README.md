# News Chatbot Backend

A RAG-powered chatbot backend for answering queries about news articles using FastAPI, Redis, and Gemini AI.

![GitHub Actions Status](https://github.com/RahulGopathi/NewsChatbot-BE/workflows/Build%20and%20Push%20Docker%20Image/badge.svg)

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

The application can be run entirely using Docker Compose:

```bash
# Create a .env file with your configuration
cp .env.example .env

# Edit the .env file with your API keys
nano .env

# Start all services including the API
docker-compose up -d
```

The API will be available at `http://localhost:8000`

For development, you can run only the dependencies and the API separately:

```bash
# Start only Redis and Qdrant
docker-compose up -d redis qdrant

# Run the API with hot-reload for development
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

## Docker Setup

The application includes a Dockerfile and Docker Compose configuration for easy deployment:

### Building the Docker Image Locally

```bash
# Build the Docker image
docker build -t newschatbot-be .

# Run the container
docker run -p 8000:8000 --env-file .env newschatbot-be
```

### Using GitHub Container Registry

After pushing to GitHub, the GitHub Actions workflow will automatically build and publish the Docker image. To use it:

```bash
# Pull the image
docker pull ghcr.io/username/newschatbot-be:latest

# Run the container
docker run -p 8000:8000 --env-file .env ghcr.io/username/newschatbot-be:latest
```

Replace `username` with your GitHub username or organization.

## GitHub Actions CI/CD

The repository includes a GitHub Actions workflow that:

1. Builds the Docker image only when a tag starting with "v" is pushed (e.g., v1.0.0)
2. Tags the Docker image based on the git tag
3. Pushes the image to GitHub Container Registry

To enable the GitHub Actions workflow:

1. Go to your repository settings on GitHub
2. Navigate to "Actions" > "General"
3. Ensure "Read and write permissions" is selected under "Workflow permissions"

For more details, see the workflow file at `.github/workflows/docker-build.yml`.

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
