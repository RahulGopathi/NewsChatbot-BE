import argparse
import logging
from app.services.news_service import NewsService
from app.core.logging import setup_logging

# Set up logging
logger = setup_logging()


def main():
    """Run the news ingestion service."""
    parser = argparse.ArgumentParser(description="Ingest news articles from Reuters.")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of articles to ingest (default: 50)",
    )
    args = parser.parse_args()

    logger.info(f"Starting news ingestion with limit of {args.limit} articles")

    try:
        service = NewsService()
        articles_processed = service.ingest_news(article_limit=args.limit)

        logger.info(
            f"News ingestion completed. Processed {articles_processed} articles."
        )
    except Exception as e:
        logger.error(f"Error in news ingestion script: {str(e)}")


if __name__ == "__main__":
    main()
