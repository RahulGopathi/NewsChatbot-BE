from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.core.config import get_settings
from app.rag.embeddings import EmbeddingGenerator
import uuid
import hashlib

settings = get_settings()
logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, collection_name: str = "news_articles"):
        logger.info(f"Initializing VectorStore with collection: {collection_name}")
        self.collection_name = collection_name
        self.embedding_generator = EmbeddingGenerator()
        self.is_in_memory = settings.VECTOR_STORE_IN_MEMORY

        # Initialize Qdrant client based on configuration
        if settings.VECTOR_STORE_IN_MEMORY:
            # In-memory Qdrant for testing
            logger.info("Using in-memory Qdrant database")
            self.client = QdrantClient(":memory:")
        elif settings.VECTOR_STORE_LOCAL_PATH:
            # Local persistence
            logger.info(
                f"Using local Qdrant database at {settings.VECTOR_STORE_LOCAL_PATH}"
            )
            self.client = QdrantClient(path=settings.VECTOR_STORE_LOCAL_PATH)
        else:
            # Remote Qdrant server
            logger.info(
                f"Connecting to Qdrant server at {settings.VECTOR_STORE_HOST}:{settings.VECTOR_STORE_PORT}"
            )
            self.client = QdrantClient(
                host=settings.VECTOR_STORE_HOST, port=settings.VECTOR_STORE_PORT
            )

        self._ensure_collection_exists()
        logger.info(f"VectorStore initialization complete")

    def _ensure_valid_id(self, point_id: str) -> str:
        """
        Ensure the ID is a valid Qdrant point ID (UUID or unsigned integer)
        """
        # If it's already a valid UUID, return it
        try:
            uuid.UUID(point_id)
            logger.debug(f"ID '{point_id}' is already a valid UUID")
            return point_id
        except ValueError:
            # Not a UUID, check if it's an integer
            if point_id.isdigit():
                logger.debug(f"ID '{point_id}' is a valid unsigned integer")
                return point_id
            else:
                # Convert string to UUID format
                logger.debug(f"Converting string ID '{point_id}' to UUID format")
                return self._string_to_uuid(point_id)

    def _string_to_uuid(self, input_string: str) -> str:
        """
        Convert a string to a valid UUID by hashing it and formatting as UUID
        """
        # Create a hash of the input string
        hash_object = hashlib.md5(input_string.encode())
        hex_dig = hash_object.hexdigest()

        # Format the hash as a UUID (8-4-4-4-12 format)
        result = str(uuid.UUID(hex_dig))
        logger.debug(f"Converted string ID '{input_string}' to UUID: {result}")
        return result

    def _ensure_collection_exists(self):
        """Ensure the collection exists in the vector store"""
        logger.debug(f"Checking if collection '{self.collection_name}' exists")
        collections = self.client.get_collections().collections
        collection_names = [collection.name for collection in collections]

        if self.collection_name not in collection_names:
            logger.info(f"Creating collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.embedding_generator.embedding_dim,
                    distance=models.Distance.COSINE,
                ),
            )

            # Create payload indexes for efficient filtering
            self._create_payload_indexes()
        else:
            logger.debug(f"Collection '{self.collection_name}' already exists")

    def _create_payload_indexes(self):
        """Create payload indexes for efficient filtering"""
        logger.info(f"Creating payload indexes for collection '{self.collection_name}'")
        try:
            # Index for date-based queries
            logger.debug("Creating date_publish index")
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="date_publish",
                field_schema=models.PayloadSchemaType.DATETIME,
            )

            # Index for source domain filtering
            logger.debug("Creating source_domain index")
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="source_domain",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

            # Index for categories filtering
            logger.debug("Creating categories index")
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="categories",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

            logger.info("Successfully created all payload indexes")

        except Exception as e:
            logger.warning(f"Error creating payload indexes: {str(e)}")

    async def add_documents(
        self, documents: List[Dict[str, Any]], embeddings: List[List[float]]
    ):
        """Add documents and their embeddings to the vector store"""
        if not documents or not embeddings:
            logger.warning("No documents or embeddings to add")
            return

        if len(documents) != len(embeddings):
            logger.error(
                f"Count mismatch: {len(documents)} documents vs {len(embeddings)} embeddings"
            )
            raise ValueError(
                f"Number of documents ({len(documents)}) does not match "
                f"number of embeddings ({len(embeddings)})"
            )

        logger.info(f"Preparing to add {len(documents)} documents to vector store")
        points = []
        for doc, embedding in zip(documents, embeddings):
            # Use the document's ID field instead of sequential numbering
            if "id" not in doc:
                logger.warning(
                    f"Document missing ID field, skipping: {doc.get('title', 'Unknown')}"
                )
                continue

            # Convert datetime objects to ISO strings for Qdrant
            doc_copy = doc.copy()
            if isinstance(doc_copy.get("date_publish"), datetime):
                doc_copy["date_publish"] = doc_copy["date_publish"].isoformat()

            # Store the original ID in the payload
            doc_copy["original_id"] = doc["id"]

            # Ensure the ID is a valid UUID or unsigned integer for Qdrant
            point_id = self._ensure_valid_id(doc["id"])

            points.append(
                models.PointStruct(id=point_id, vector=embedding, payload=doc_copy)
            )

        if not points:
            logger.warning("No valid points to add")
            return

        try:
            logger.debug(
                f"Upserting {len(points)} points to collection '{self.collection_name}'"
            )
            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info(f"Successfully added {len(points)} documents to vector store")
        except Exception as e:
            logger.error(f"Error adding documents to vector store: {str(e)}")
            raise

    async def update_document(
        self, document_id: str, document: Dict[str, Any], embedding: List[float]
    ):
        """Update an existing document in the vector store"""
        # Convert datetime objects to ISO strings for Qdrant
        doc_copy = document.copy()
        if isinstance(doc_copy.get("date_publish"), datetime):
            doc_copy["date_publish"] = doc_copy["date_publish"].isoformat()

        # Store the original ID in the payload
        doc_copy["original_id"] = document_id

        # Ensure the ID is a valid UUID or unsigned integer for Qdrant
        point_id = self._ensure_valid_id(document_id)

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(id=point_id, vector=embedding, payload=doc_copy)
                ],
            )
            logger.info(f"Updated document {document_id} in vector store")
        except Exception as e:
            logger.error(f"Error updating document {document_id}: {str(e)}")
            raise

    async def delete_documents(self, document_ids: List[str]):
        """Delete documents from the vector store by ID"""
        try:
            # Ensure all IDs are valid Qdrant point IDs
            valid_point_ids = [self._ensure_valid_id(doc_id) for doc_id in document_ids]

            logger.info(
                f"Deleting {len(valid_point_ids)} documents from collection '{self.collection_name}'"
            )
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=valid_point_ids,
                ),
            )
            logger.info(
                f"Successfully deleted {len(document_ids)} documents from vector store"
            )
        except Exception as e:
            logger.error(f"Error deleting documents: {str(e)}")
            raise

    async def search(
        self,
        query_embedding: List[float],
        limit: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        source_domains: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents using query embedding with filtering options

        Parameters:
        - query_embedding: The query embedding vector
        - limit: Maximum number of results to return
        - start_date: Filter articles published after this date
        - end_date: Filter articles published before this date
        - source_domains: Filter articles from these source domains
        - categories: Filter articles with these categories
        """
        if limit is None:
            limit = settings.TOP_K_RESULTS

        search_params = {
            "collection_name": self.collection_name,
            "query_vector": query_embedding,
            "limit": limit,
        }

        # Build filter conditions
        filter_conditions = []

        # Date range filter
        if start_date or end_date:
            date_condition = {}
            if start_date:
                date_condition["gte"] = start_date.isoformat()
            if end_date:
                date_condition["lte"] = end_date.isoformat()

            filter_conditions.append(
                models.FieldCondition(
                    key="date_publish", range=models.Range(**date_condition)
                )
            )

        # Source domain filter
        if source_domains:
            filter_conditions.append(
                models.FieldCondition(
                    key="source_domain", match=models.MatchAny(any=source_domains)
                )
            )

        # Categories filter
        if categories:
            filter_conditions.append(
                models.FieldCondition(
                    key="categories", match=models.MatchAny(any=categories)
                )
            )

        # Prepare filter if any conditions exist
        if filter_conditions:
            search_params["query_filter"] = models.Filter(must=filter_conditions)

        try:
            logger.info(
                f"Searching collection '{self.collection_name}' with limit {limit}"
            )
            search_result = self.client.search(**search_params)

            logger.info(f"Found {len(search_result)} results")
            return [hit.payload for hit in search_result]
        except Exception as e:
            logger.error(f"Error searching vector store: {str(e)}")
            raise

    async def search_by_date(
        self,
        query_embedding: List[float],
        days: int = 1,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for recent articles within the specified number of days

        This is a convenience method for common "recent news" queries
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        logger.info(f"Searching for articles in the last {days} days")
        return await self.search(
            query_embedding=query_embedding,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by its ID"""
        try:
            # Ensure the ID is a valid UUID or unsigned integer for Qdrant
            point_id = self._ensure_valid_id(document_id)

            logger.info(
                f"Retrieving document with ID '{document_id}' (converted to '{point_id}')"
            )
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id],
            )

            if not points:
                logger.warning(f"Document with ID '{document_id}' not found")
                return None

            logger.info(f"Successfully retrieved document with ID '{document_id}'")
            return points[0].payload
        except Exception as e:
            logger.error(f"Error retrieving document {document_id}: {str(e)}")
            return None
