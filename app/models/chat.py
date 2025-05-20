from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid


class Message(BaseModel):
    id: str = str(uuid.uuid4())
    role: str
    content: str
    timestamp: datetime = datetime.now()

    class Config:
        json_encoders = {datetime: lambda dt: dt.isoformat()}


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: datetime = datetime.now()

    class Config:
        json_encoders = {datetime: lambda dt: dt.isoformat()}


class ChatHistory(BaseModel):
    session_id: str
    messages: List[Message]
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

    class Config:
        json_encoders = {datetime: lambda dt: dt.isoformat()}
