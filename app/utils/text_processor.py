import json
import os
import re
import uuid
from datetime import datetime
from typing import List, Dict, Any

from app.models.news import RawNewsArticle, NewsChunk, Category


def load_raw_article(file_path: str) -> RawNewsArticle:
    """
    Load a raw news article from a JSON file
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Convert categories list to Category objects if needed
    if isinstance(data.get("categories", []), list):
        data["categories"] = [
            c if isinstance(c, dict) else {"value": c, "domain": "unknown"}
            for c in data.get("categories", [])
        ]

    return RawNewsArticle(**data)


def prepare_article(article: RawNewsArticle) -> Dict[str, Any]:
    """
    Prepare article data for further processing
    """
    # Extract article ID from filename or generate one
    article_id = os.path.basename(article.url).split(".")[0]
    if not article_id:
        article_id = str(uuid.uuid4())

    # Parse date string to datetime object
    try:
        date_publish = datetime.fromisoformat(article.date_publish)
    except (ValueError, TypeError):
        date_publish = datetime.now()

    # Extract category values
    category_values = [cat.value for cat in article.categories]

    return {
        "article_id": article_id,
        "title": article.title,
        "text": article.text,
        "url": article.url,
        "date_publish": date_publish,
        "source_domain": article.source_domain,
        "categories": category_values,
        "description": article.description,
    }


def chunk_article(
    prepared_article: Dict[str, Any], max_chunk_size: int = 1000
) -> List[NewsChunk]:
    """
    Split article text into chunks for embedding
    """
    article_id = prepared_article["article_id"]
    full_text = prepared_article["text"]

    # Split text by paragraphs (preferred) or sentences
    paragraphs = re.split(r"\n+", full_text)
    chunks = []
    current_chunk = ""
    chunk_index = 0

    for paragraph in paragraphs:
        # If adding this paragraph would exceed max size, create a new chunk
        if len(current_chunk) + len(paragraph) > max_chunk_size and current_chunk:
            # Create chunk with all metadata
            chunk_id = f"{article_id}_{chunk_index}"
            chunks.append(
                NewsChunk(
                    id=chunk_id,
                    article_id=article_id,
                    title=prepared_article["title"],
                    text=current_chunk,
                    url=prepared_article["url"],
                    date_publish=prepared_article["date_publish"],
                    source_domain=prepared_article["source_domain"],
                    categories=prepared_article["categories"],
                    description=prepared_article["description"],
                    metadata={
                        "chunk_index": chunk_index,
                        "is_first_chunk": chunk_index == 0,
                    },
                )
            )
            current_chunk = paragraph
            chunk_index += 1
        else:
            # Add to current chunk
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph

    # Don't forget the last chunk
    if current_chunk:
        chunk_id = f"{article_id}_{chunk_index}"
        chunks.append(
            NewsChunk(
                id=chunk_id,
                article_id=article_id,
                title=prepared_article["title"],
                text=current_chunk,
                url=prepared_article["url"],
                date_publish=prepared_article["date_publish"],
                source_domain=prepared_article["source_domain"],
                categories=prepared_article["categories"],
                description=prepared_article["description"],
                metadata={
                    "chunk_index": chunk_index,
                    "is_first_chunk": chunk_index == 0,
                    "is_last_chunk": True,
                },
            )
        )

    # Mark last chunk
    if chunks:
        chunks[-1].metadata["is_last_chunk"] = True

    return chunks


def process_article_file(file_path: str, max_chunk_size: int = 1000) -> List[NewsChunk]:
    """
    Process a single article file into chunks ready for embedding
    """
    raw_article = load_raw_article(file_path)
    prepared_article = prepare_article(raw_article)
    return chunk_article(prepared_article, max_chunk_size)
