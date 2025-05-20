from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.v1.endpoints import chat, news
from app.core.logging import setup_logging

# Initialize logging
logger = setup_logging()

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for the News Chatbot application",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix=settings.API_V1_STR + "/chat", tags=["chat"])
app.include_router(news.router, prefix=settings.API_V1_STR + "/news", tags=["news"])


@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to News Chatbot API"}


@app.get("/health")
async def health_check():
    logger.info("Health check endpoint accessed")
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
