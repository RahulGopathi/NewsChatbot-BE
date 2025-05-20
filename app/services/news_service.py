import os
import json
import logging
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import xml.etree.ElementTree as ET
from newsplease import NewsPlease
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class NewsService:
    """Service for fetching and processing news articles from RSS feeds."""

    def __init__(self):
        self.rss_feed_urls = [
            "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        ]
        self.data_dir = os.path.join(os.getcwd(), "data")
        self.raw_articles_dir = os.path.join(self.data_dir, "raw_articles")

        # Create directory if it doesn't exist
        os.makedirs(self.raw_articles_dir, exist_ok=True)

    def fetch_article_urls_from_rss(
        self, limit: int = 50
    ) -> List[Tuple[str, List[Dict[str, str]]]]:
        """Fetch article URLs and categories from multiple RSS feeds."""
        all_article_data = []
        urls_per_feed = limit // len(
            self.rss_feed_urls
        )  # Distribute limit across feeds

        for feed_url in self.rss_feed_urls:
            try:
                logger.info(f"Fetching articles from RSS feed: {feed_url}")
                response = requests.get(feed_url)
                response.raise_for_status()

                # Parse the XML response
                root = ET.fromstring(response.content)

                # Extract article URLs and categories from RSS items
                article_count = 0
                for item in root.findall(".//item"):
                    link = item.find("link")
                    if link is not None and link.text:
                        # Extract categories
                        categories = []
                        for category in item.findall("category"):
                            category_data = {"value": category.text}
                            # Add domain attribute if it exists
                            domain = category.get("domain")
                            if domain:
                                category_data["domain"] = domain
                            categories.append(category_data)

                        all_article_data.append((link.text, categories))
                        article_count += 1

                    # Limit the number of articles per feed
                    if article_count >= urls_per_feed:
                        break

                logger.info(f"Found {article_count} articles in RSS feed: {feed_url}")

            except Exception as e:
                logger.error(
                    f"Error fetching article URLs from RSS feed {feed_url}: {str(e)}"
                )

        # If we didn't get enough articles, we can try to get more from each feed
        if len(all_article_data) < limit:
            logger.warning(
                f"Only found {len(all_article_data)} articles across all feeds, less than requested {limit}"
            )

        return all_article_data[:limit]  # Ensure we don't exceed the requested limit

    def fetch_and_parse_articles_batch(
        self, article_data: List[Tuple[str, List[Dict[str, str]]]]
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch and parse multiple articles in a batch."""
        try:
            # Extract URLs for news-please
            urls = [url for url, _ in article_data]

            # Create a mapping of URL to categories
            url_to_categories = {url: categories for url, categories in article_data}

            # Use news-please to download and parse the articles in batch
            articles = NewsPlease.from_urls(urls, request_args={"timeout": 6})

            # Process the articles
            processed_articles = {}
            for url, article in articles.items():
                if article and article.title:
                    # Get categories for this URL
                    categories = url_to_categories.get(url, [])

                    # Convert the article to a dictionary
                    article_dict = {
                        "title": article.title,
                        "text": article.maintext,
                        "url": url,
                        "authors": article.authors,
                        "date_publish": (
                            article.date_publish.isoformat()
                            if article.date_publish
                            else None
                        ),
                        "source_domain": article.source_domain,
                        "language": article.language,
                        "description": article.description,
                        "categories": categories,
                        "fetch_time": datetime.now().isoformat(),
                    }
                    processed_articles[url] = article_dict
                    logger.info(f"Successfully parsed article: {url}")
                else:
                    logger.warning(
                        f"Article could not be parsed or has no title: {url}"
                    )

            return processed_articles

        except Exception as e:
            logger.error(f"Error batch fetching articles: {str(e)}")
            return {}

    def save_article(self, article: Dict[str, Any]) -> bool:
        """Save an article to disk."""
        try:
            if not article or not article.get("title"):
                return False

            # Create a safe filename from the title
            title = article["title"]
            safe_title = "".join([c if c.isalnum() else "_" for c in title])
            safe_title = safe_title[:100]  # Limit length

            # Add a timestamp to ensure uniqueness
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{safe_title}_{timestamp}.json"

            # Save the article to disk
            file_path = os.path.join(self.raw_articles_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(article, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved article: {file_path}")
            return True

        except Exception as e:
            logger.error(
                f"Error saving article {article.get('title', 'Unknown')}: {str(e)}"
            )
            return False

    def ingest_news(self, article_limit: int = 50) -> int:
        """Main method to ingest news articles."""
        articles_processed = 0

        try:
            # Fetch article URLs from RSS feeds
            article_data = self.fetch_article_urls_from_rss(limit=article_limit)

            if not article_data:
                logger.error("No article URLs found in any RSS feeds")
                return 0

            logger.info(
                f"Collected {len(article_data)} article URLs for processing from multiple feeds"
            )

            # Process articles in batches of 10
            batch_size = 10
            for i in range(0, len(article_data), batch_size):
                batch_data = article_data[i : i + batch_size]

                # Fetch and parse batch of articles
                articles_batch = self.fetch_and_parse_articles_batch(batch_data)

                # Save each article
                for url, article in articles_batch.items():
                    success = self.save_article(article)
                    if success:
                        articles_processed += 1

                logger.info(
                    f"Processed batch of {len(batch_data)} URLs, saved {len(articles_batch)} articles"
                )

            logger.info(f"Successfully ingested {articles_processed} articles")
            return articles_processed

        except Exception as e:
            logger.error(f"Error in news ingestion process: {str(e)}")
            return articles_processed
