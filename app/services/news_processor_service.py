import os
import glob
from typing import List, Dict, Any, Optional
import logging

from app.utils.text_processor import process_article_file
from app.models.news import NewsChunk
from app.rag.embeddings import EmbeddingGenerator
from app.rag.vector_store import VectorStore
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class NewsProcessorService:
    def __init__(self):
        self.embedding_generator = EmbeddingGenerator()
        self.vector_store = VectorStore()
        logger.info("NewsProcessorService initialized")

    async def process_directory(self, directory_path: str) -> int:
        """
        Process all JSON news article files in a directory
        Returns the number of articles processed
        """
        # Find all JSON files in the directory
        file_paths = glob.glob(os.path.join(directory_path, "*.json"))
        logger.info(f"Found {len(file_paths)} JSON files in {directory_path}")

        total_processed = 0
        for file_path in file_paths:
            try:
                chunks = await self.process_single_file(file_path)
                if chunks:
                    total_processed += 1
                    logger.info(
                        f"Successfully processed {file_path} into {len(chunks)} chunks"
                    )
                else:
                    logger.warning(f"No chunks created for {file_path}")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")

        return total_processed

    async def process_single_file(self, file_path: str) -> List[NewsChunk]:
        """
        Process a single news article file
        Returns the list of chunks created
        """
        logger.info(f"Processing file: {file_path}")

        # Process the file into chunks
        chunks = process_article_file(file_path)

        if not chunks:
            logger.warning(f"No chunks generated for file: {file_path}")
            return []

        # Convert chunks to dictionaries for vector store
        chunk_dicts = []
        chunk_texts = []

        # First extract article_id to check if we need to delete existing chunks
        article_id = chunks[0].article_id if chunks else None

        if article_id:
            # Check if this article already exists and delete if it does
            await self._delete_existing_article_chunks(article_id)

        for chunk in chunks:
            # Prepare text for embedding
            # Combine title, description (if available) and chunk text for context
            embed_text = chunk.title
            if chunk.description:
                embed_text += f" {chunk.description}"
            embed_text += f" {chunk.text}"

            # Convert to dict and make sure ID is a string for Qdrant
            chunk_dict = chunk.model_dump()
            # Make sure id is a string type
            chunk_dict["id"] = str(chunk_dict["id"])

            # Add to lists for batch processing
            chunk_dicts.append(chunk_dict)
            chunk_texts.append(embed_text)

        # Generate embeddings for all chunks
        logger.info(f"Generating embeddings for {len(chunk_texts)} chunks")
        embeddings = await self.embedding_generator.generate_embeddings(chunk_texts)

        if len(embeddings) != len(chunk_dicts):
            logger.warning(
                f"Mismatch between chunks ({len(chunk_dicts)}) and embeddings ({len(embeddings)})"
            )
            # Only process chunks that have embeddings
            chunk_dicts = chunk_dicts[: len(embeddings)]

        # Store in vector database
        await self.vector_store.add_documents(chunk_dicts, embeddings)

        logger.info(f"Processed file {file_path} into {len(chunks)} chunks")
        return chunks

    async def _delete_existing_article_chunks(self, article_id: str) -> None:
        """
        Delete existing chunks for an article before re-indexing
        This prevents duplicate content when reprocessing an article
        """
        try:
            logger.info(f"Deleting existing chunks for article: {article_id}")

            # Since our chunk IDs follow the pattern article_id_chunk_index
            # We'll build a list of possible chunk IDs to delete
            # Assuming max 20 chunks per article is reasonable
            chunk_ids = [f"{article_id}_{i}" for i in range(20)]

            # Try to delete all potential chunk IDs
            await self.vector_store.delete_documents(chunk_ids)
            logger.info(f"Deleted existing chunks for article: {article_id}")
        except Exception as e:
            logger.warning(
                f"Error deleting existing chunks for article {article_id}: {str(e)}"
            )
