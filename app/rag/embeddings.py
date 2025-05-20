from typing import List, Optional
import logging
import httpx
import asyncio
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.api_key = settings.JINA_API_KEY
        self.api_url = "https://api.jina.ai/v1/embeddings"
        self.embedding_dim = self.get_embedding_dimension()
        logger.info(
            f"Initialized EmbeddingGenerator with model: {self.model_name}, dimension: {self.embedding_dim}"
        )

    def get_embedding_dimension(self) -> int:
        """
        Get the embedding dimension from the model
        Default to 768 if unable to determine
        """
        # Different Jina models have different dimensions
        # jina-embeddings-v2: 768
        # jina-embeddings-v3: 1024
        model_dimensions = {"jina-embeddings-v2": 768, "jina-embeddings-v3": 1024}

        dimension = model_dimensions.get(self.model_name, 768)
        logger.debug(
            f"Using embedding dimension: {dimension} for model: {self.model_name}"
        )
        return dimension

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using Jina API

        This version handles empty or invalid inputs better and logs meaningful errors
        for news article content.
        """
        if not texts:
            logger.warning("Received empty text list for embedding")
            return []

        try:
            # Filter out empty texts
            valid_texts = [text for text in texts if text and isinstance(text, str)]
            if len(valid_texts) != len(texts):
                logger.warning(
                    f"Filtered out {len(texts) - len(valid_texts)} invalid texts"
                )

            if not valid_texts:
                return []

            logger.info(f"Generating embeddings for {len(valid_texts)} texts")

            # Prepare the API request payload
            payload = {
                "model": self.model_name,
                "task": "text-matching",
                "input": valid_texts,
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            # Make API request
            logger.debug(f"Sending request to Jina API: {self.api_url}")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url, json=payload, headers=headers, timeout=30.0
                )

                if response.status_code != 200:
                    logger.error(f"API error: {response.status_code} - {response.text}")
                    raise Exception(
                        f"API error: {response.status_code} - {response.text}"
                    )

                result = response.json()

                # Extract embeddings from the response
                embeddings = [data["embedding"] for data in result["data"]]
                logger.info(f"Successfully generated {len(embeddings)} embeddings")
                return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            if len(texts) > 5:
                sample = texts[:5]
            else:
                sample = texts
            logger.debug(f"Sample of texts causing error: {sample}")
            raise Exception(f"Error generating embeddings: {str(e)}")

    async def generate_single_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        """
        if not text or not isinstance(text, str):
            logger.warning("Received invalid text for embedding")
            raise ValueError("Text must be a non-empty string")

        try:
            logger.info("Generating single embedding")
            embeddings = await self.generate_embeddings([text])
            logger.debug("Successfully generated single embedding")
            return embeddings[0]
        except Exception as e:
            logger.error(f"Error generating embedding for text: {str(e)}")
            # Log a sample of the text that caused the error
            text_sample = text[:100] + "..." if len(text) > 100 else text
            logger.debug(f"Text causing error: {text_sample}")
            raise Exception(f"Error generating embedding: {str(e)}")
