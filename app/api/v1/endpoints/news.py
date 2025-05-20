from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from typing import List, Optional
import os
from datetime import datetime

from app.services.news_processor_service import NewsProcessorService

router = APIRouter()
news_processor = NewsProcessorService()


class ProcessDirectoryRequest(BaseModel):
    directory_path: str


class ProcessFileRequest(BaseModel):
    file_path: str


class ProcessResponse(BaseModel):
    message: str
    processed_count: int


class NewsSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = None
    recent_days: Optional[int] = None
    source_domains: Optional[List[str]] = None
    categories: Optional[List[str]] = None


class NewsArticle(BaseModel):
    id: str
    title: str
    text: str
    url: str
    date_publish: str
    source_domain: str
    categories: List[str]
    description: Optional[str] = None
    metadata: Optional[dict] = None


class NewsSearchResponse(BaseModel):
    results: List[NewsArticle]
    count: int


@router.post("/process-directory", response_model=ProcessResponse)
async def process_directory(request: ProcessDirectoryRequest):
    """
    Process all news articles in a directory
    """
    if not os.path.isdir(request.directory_path):
        raise HTTPException(status_code=400, detail="Invalid directory path")

    processed_count = await news_processor.process_directory(request.directory_path)

    return {
        "message": f"Successfully processed {processed_count} news articles",
        "processed_count": processed_count,
    }


@router.post("/process-file", response_model=ProcessResponse)
async def process_file(request: ProcessFileRequest):
    """
    Process a single news article file
    """
    if not os.path.isfile(request.file_path):
        raise HTTPException(status_code=400, detail="Invalid file path")

    chunks = await news_processor.process_single_file(request.file_path)

    return {
        "message": f"Successfully processed file into {len(chunks)} chunks",
        "processed_count": 1 if chunks else 0,
    }


@router.post("/search", response_model=NewsSearchResponse)
async def search_news(request: NewsSearchRequest):
    """
    Search for news articles matching the query with optional filters
    """
    try:
        results = await news_processor.search_news(
            query=request.query,
            limit=request.limit,
            recent_days=request.recent_days,
            source_domains=request.source_domains,
            categories=request.categories,
        )

        # Convert results to response model
        formatted_results = []
        for result in results:
            # Ensure date_publish is a string
            if isinstance(result.get("date_publish"), datetime):
                result["date_publish"] = result["date_publish"].isoformat()

            # Format the result into NewsArticle model
            formatted_results.append(NewsArticle(**result))

        return {"results": formatted_results, "count": len(formatted_results)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error searching news articles: {str(e)}"
        )


@router.get("/search", response_model=NewsSearchResponse)
async def search_news_get(
    query: str = Query(..., description="Search query"),
    limit: Optional[int] = Query(
        None, description="Maximum number of results to return"
    ),
    recent_days: Optional[int] = Query(
        None, description="Limit results to the last N days"
    ),
    source_domain: Optional[str] = Query(None, description="Filter by source domain"),
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """
    Search for news articles matching the query with optional filters (GET version)
    """
    # Convert single values to lists for the service
    source_domains = [source_domain] if source_domain else None
    categories = [category] if category else None

    try:
        results = await news_processor.search_news(
            query=query,
            limit=limit,
            recent_days=recent_days,
            source_domains=source_domains,
            categories=categories,
        )

        # Convert results to response model
        formatted_results = []
        for result in results:
            # Ensure date_publish is a string
            if isinstance(result.get("date_publish"), datetime):
                result["date_publish"] = result["date_publish"].isoformat()

            # Format the result into NewsArticle model
            formatted_results.append(NewsArticle(**result))

        return {"results": formatted_results, "count": len(formatted_results)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error searching news articles: {str(e)}"
        )


def process_directory_background(directory_path: str):
    """
    Background task to process a directory
    """
    import asyncio

    async def run_process():
        await news_processor.process_directory(directory_path)

    asyncio.run(run_process())


@router.post("/process-directory-background")
async def process_directory_in_background(
    request: ProcessDirectoryRequest, background_tasks: BackgroundTasks
):
    """
    Process all news articles in a directory as a background task
    """
    if not os.path.isdir(request.directory_path):
        raise HTTPException(status_code=400, detail="Invalid directory path")

    background_tasks.add_task(process_directory_background, request.directory_path)

    return {"message": f"Started processing directory: {request.directory_path}"}
