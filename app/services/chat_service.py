import json
from typing import List, Optional, Dict, Any
import redis
from datetime import datetime, timedelta
import logging
from app.core.config import get_settings
from app.models.chat import Message, ChatHistory
from app.rag.embeddings import EmbeddingGenerator
from app.rag.vector_store import VectorStore
from app.rag.query_analyzer import QueryAnalyzer
from google import genai

settings = get_settings()
logger = logging.getLogger(__name__)

# Configure Gemini
client = genai.Client(api_key=settings.GEMINI_API_KEY)


class ChatService:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )
        self.embedding_generator = EmbeddingGenerator()
        self.vector_store = VectorStore()
        self.query_analyzer = QueryAnalyzer()

    def _get_session_key(self, session_id: str) -> str:
        return f"chat:session:{session_id}"

    async def create_session(self, session_id: str) -> ChatHistory:
        """Create a new chat session"""
        chat_history = ChatHistory(
            session_id=session_id,
            messages=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        await self.save_session(chat_history)
        return chat_history

    async def get_session(self, session_id: str) -> Optional[ChatHistory]:
        """Get chat session by ID"""
        session_key = self._get_session_key(session_id)
        session_data = self.redis_client.get(session_key)

        if not session_data:
            return None

        session_dict = json.loads(session_data)
        messages = [Message(**msg) for msg in session_dict["messages"]]

        return ChatHistory(
            session_id=session_id,
            messages=messages,
            created_at=datetime.fromisoformat(session_dict["created_at"]),
            updated_at=datetime.fromisoformat(session_dict["updated_at"]),
        )

    async def save_session(self, chat_history: ChatHistory):
        """Save chat session to Redis"""
        session_key = self._get_session_key(chat_history.session_id)

        # Convert Message objects to dictionaries with properly formatted timestamps
        messages_data = []
        for msg in chat_history.messages:
            msg_dict = {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            }
            messages_data.append(msg_dict)

        session_data = {
            "session_id": chat_history.session_id,
            "messages": messages_data,
            "created_at": chat_history.created_at.isoformat(),
            "updated_at": chat_history.updated_at.isoformat(),
        }
        self.redis_client.set(session_key, json.dumps(session_data))

    async def add_message(self, session_id: str, message: Message):
        """Add a message to the chat session"""
        chat_history = await self.get_session(session_id)
        if not chat_history:
            chat_history = await self.create_session(session_id)

        chat_history.messages.append(message)
        chat_history.updated_at = datetime.now()
        await self.save_session(chat_history)

    async def clear_session(self, session_id: str):
        """Clear a chat session"""
        session_key = self._get_session_key(session_id)
        self.redis_client.delete(session_key)

    async def update_message(self, message_id: str, content: str, role: str = "ai"):
        """Update the content and role of a message in the chat history"""
        # Get all sessions
        session_keys = self.redis_client.keys("chat:session:*")

        for session_key in session_keys:
            session_data = self.redis_client.get(session_key)
            if not session_data:
                continue

            session_dict = json.loads(session_data)
            messages = session_dict["messages"]

            # Find and update the message
            for msg in messages:
                if msg.get("id") == message_id:
                    msg["content"] = content
                    msg["role"] = role
                    session_dict["updated_at"] = datetime.now().isoformat()
                    self.redis_client.set(session_key, json.dumps(session_dict))
                    return

    async def retrieve_relevant_news(
        self,
        query: str,
        query_analysis: Dict[str, Any],
        limit: int = settings.TOP_K_RESULTS,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve news articles relevant to the query with optimized filters

        Parameters:
        - query: User's query
        - query_analysis: Analysis of the query type and filters
        - limit: Maximum number of articles to retrieve
        """
        try:
            # Generate query embedding directly
            query_embedding = await self.embedding_generator.generate_single_embedding(
                query
            )

            # Extract filters from query analysis
            filters = query_analysis.get("filters", {})
            query_type = query_analysis.get("query_type", "relevance")
            ordering = query_analysis.get("ordering", "relevance")

            # Set up search parameters
            search_params = {
                "query_embedding": query_embedding,
                "limit": limit,
            }

            # Apply date filters if present, converting ISO strings to datetime objects
            if filters.get("start_date"):
                try:
                    # Parse the date string to date object without time
                    date_str = filters["start_date"]
                    # Strip time component if present
                    if "T" in date_str:
                        date_str = date_str.split("T")[0]
                    start_date = datetime.strptime(date_str, "%Y-%m-%d")
                    search_params["start_date"] = start_date
                    logger.info(f"Using start_date filter: {start_date}")
                except ValueError as e:
                    logger.error(f"Invalid start_date format: {str(e)}")

            if filters.get("end_date"):
                try:
                    # Parse the date string to date object without time
                    date_str = filters["end_date"]
                    # Strip time component if present
                    if "T" in date_str:
                        date_str = date_str.split("T")[0]
                    end_date = datetime.strptime(date_str, "%Y-%m-%d")
                    search_params["end_date"] = end_date
                    logger.info(f"Using end_date filter: {end_date}")
                except ValueError as e:
                    logger.error(f"Invalid end_date format: {str(e)}")

            # Apply category filters if present
            if filters.get("categories"):
                search_params["categories"] = filters["categories"]

            # Apply source domain filters if present
            if filters.get("sources"):
                search_params["source_domains"] = filters["sources"]

            # For timeline queries, increase the result limit for better temporal coverage
            if query_type == "timeline":
                search_params["limit"] = limit * 2

            # For summarization queries, prioritize recency
            if query_type == "summary" and not filters.get("start_date"):
                # Set start date to 7 days ago if not specified
                search_params["start_date"] = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) - timedelta(days=7)

            # Search vector store directly
            relevant_articles = await self.vector_store.search(**search_params)

            # Post-process results based on ordering
            if ordering == "chronological" or query_type == "timeline":
                relevant_articles.sort(key=lambda x: x.get("date_publish", ""))

            # Format articles for chat context
            formatted_articles = []

            for article in relevant_articles:
                # Format date
                date_str = article.get("date_publish", "")
                if isinstance(date_str, datetime):
                    date_str = date_str.strftime("%Y-%m-%d")

                # Create a formatted entry with essential information
                formatted_article = {
                    "title": article.get("title", ""),
                    "source": article.get("source_domain", ""),
                    "date": date_str,
                    "text": article.get("text", ""),
                    "url": article.get("url", ""),
                }

                formatted_articles.append(formatted_article)

            return formatted_articles
        except Exception as e:
            logger.error(f"Error retrieving relevant news: {str(e)}")
            return []

    async def process_message(
        self, user_message: str, session_id: str
    ) -> Dict[str, Any]:
        """
        Process a user message and return a response with relevant context

        Parameters:
        - user_message: The user's message
        - session_id: Chat session ID

        Returns a dictionary with the bot response and context used
        """
        # Get chat history
        chat_history = await self.get_session(session_id)
        if not chat_history:
            chat_history = await self.create_session(session_id)

        # Add user message to history
        user_msg = Message(role="user", content=user_message)
        await self.add_message(session_id, user_msg)

        try:
            # Analyze the query to determine type and filters
            query_analysis = await self.query_analyzer.analyze_query(user_message)

            print(json.dumps(query_analysis, indent=4))

            # Retrieve relevant news context with optimized filters
            relevant_news = await self.retrieve_relevant_news(
                query=user_message,
                query_analysis=query_analysis,
                limit=settings.TOP_K_RESULTS,
            )

            # Generate response using Gemini AI with the retrieved context
            context_text = ""

            # Use more articles for timelines, fewer for other query types
            article_limit = 10 if query_analysis.get("query_type") == "timeline" else 8

            for i, article in enumerate(relevant_news[:article_limit]):
                # Format article reference for context with clearer source numbering
                context_text += f"\n\nArticle {i+1}: {article['title']} ({article['source']}, {article['date']})\n"
                context_text += f"URL: {article['url']}\n"

                context_text += f"{article['text']}\n"

            # Create an optimized prompt based on query type
            prompt = self.query_analyzer.create_prompt_for_query_type(
                user_query=user_message,
                context_text=context_text,
                query_type=query_analysis.get("query_type", "relevance"),
            )

            logger.info(
                "=========================== PROMPT ==============================="
            )
            logger.info(prompt)
            logger.info(
                "=================================================================="
            )

            # Generate streaming response with Gemini using synchronous streaming
            response_stream = client.models.generate_content_stream(
                model="gemini-2.0-flash-001",
                contents=prompt,
            )

            return {
                "stream": response_stream,
            }

        except Exception as e:
            logger.error(f"Error generating response with Gemini: {str(e)}")
            error_msg = "I'm sorry, I encountered an error while processing your request. Please try again later."
            bot_msg = Message(role="ai", content=error_msg)
            await self.add_message(session_id, bot_msg)
            return {"stream": None, "context_used": [], "message_id": bot_msg.id}
