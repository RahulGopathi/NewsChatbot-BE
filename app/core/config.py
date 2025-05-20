from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "News Chatbot API"

    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # RAG Settings
    VECTOR_STORE_HOST: str = "localhost"
    VECTOR_STORE_PORT: int = 6333
    EMBEDDING_MODEL: str = "jina-embeddings-v3"
    TOP_K_RESULTS: int = 3
    # Use in-memory Qdrant for testing
    VECTOR_STORE_IN_MEMORY: bool = False
    # Local persistence path (if not using host/port)
    VECTOR_STORE_LOCAL_PATH: Optional[str] = None

    # Jina API Settings
    JINA_API_KEY: Optional[str] = None

    # Gemini API Settings
    GEMINI_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
