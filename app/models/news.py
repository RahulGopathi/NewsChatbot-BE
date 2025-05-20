from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class Category(BaseModel):
    value: str
    domain: Optional[str] = None


class RawNewsArticle(BaseModel):
    """Model representing the raw news article as ingested from JSON files"""

    title: str
    text: str
    url: str
    authors: List[str]
    date_publish: str
    source_domain: str
    language: str
    description: Optional[str] = None
    categories: List[Category] = []
    fetch_time: str


class NewsChunk(BaseModel):
    """Model representing a chunk of a news article for embedding"""

    id: str = Field(..., description="Unique identifier for the chunk")
    article_id: str = Field(..., description="Original article identifier")
    title: str = Field(..., description="Article title")
    text: str = Field(..., description="Chunk text content")
    url: str = Field(..., description="Article URL")
    date_publish: datetime = Field(..., description="Publication date")
    source_domain: str = Field(..., description="Source domain")
    categories: List[str] = Field(default=[], description="Article categories")
    description: Optional[str] = Field(None, description="Article description")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
