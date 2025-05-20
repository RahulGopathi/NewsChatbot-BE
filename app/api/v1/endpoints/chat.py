from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from app.models.chat import ChatRequest, ChatResponse, Message
from app.services.chat_service import ChatService
from google import genai
from app.core.config import get_settings
from pydantic import BaseModel
import uuid
import json

router = APIRouter()
settings = get_settings()
chat_service = ChatService()


# Simplified chat request that only contains the essential fields
class ContextSource(BaseModel):
    title: str
    source: str
    url: str


class DetailedChatResponse(ChatResponse):
    """Enhanced response with context sources used"""

    context_sources: List[ContextSource] = []


@router.post("/query")
async def chat(request: ChatRequest):
    """
    Process a chat message and return a streaming response
    Utilizes the News Chatbot RAG pipeline
    """
    try:
        # Process the message using the enhanced chat service
        result = await chat_service.process_message(
            user_message=request.message,
            session_id=request.session_id,
        )

        async def generate_stream():
            # Send START event with proper SSE format
            yield f"data: {json.dumps({'type': 'START'})}\n\n"

            # Send context sources
            if result["context_used"]:
                yield f"data: {json.dumps({'type': 'CONTEXT', 'context_sources': [ContextSource(**source).dict() for source in result['context_used']]})}\n\n"

            # Stream the response
            if result["stream"]:
                full_response = ""
                try:
                    # Don't use async for - the Gemini stream is synchronous
                    for chunk in result["stream"]:
                        if hasattr(chunk, "text"):
                            full_response += chunk.text
                            yield f"data: {json.dumps({'type': 'MESSAGE', 'role': 'ai', 'message': chunk.text})}\n\n"
                except Exception as e:
                    # If there's an error in stream processing, log it and yield it
                    error_msg = f"Error processing stream: {str(e)}"
                    print(error_msg)
                    yield f"data: {json.dumps({'type': 'ERROR', 'message': error_msg})}\n\n"

                # Add the complete response as a new message instead of updating
                complete_message = Message(
                    role="ai", content=full_response or "No response generated"
                )
                await chat_service.add_message(request.session_id, complete_message)

            # Send END event
            yield f"data: {json.dumps({'type': 'END'})}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """
    Get chat history for a session
    """
    chat_history = await chat_service.get_session(session_id)
    if not chat_history:
        raise HTTPException(status_code=404, detail="Session not found")
    return chat_history


@router.delete("/clear/{session_id}")
async def clear_session(session_id: str):
    """
    Clear a chat session
    """
    await chat_service.clear_session(session_id)
    return {"message": "Session cleared successfully"}


@router.post("/session")
async def create_session():
    """
    Create a new chat session and return the session ID
    """
    try:
        # Generate a unique session ID
        session_id = str(uuid.uuid4())

        # Create a new session
        await chat_service.create_session(session_id)

        return {"session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
