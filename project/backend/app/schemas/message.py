import json
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    content: str = Field(..., min_length=1, max_length=2000)
    content_type: str = Field(default="text", pattern="^(text|image|emoji|voice)$")
    media_url: str | None = None
    duration: int | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    role: str
    content: str
    content_type: str
    intent: str | None = None
    entities: list[dict] | None = None
    created_at: datetime


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    content_type: str
    media_url: str | None = None
    duration: int | None = None
    intent: str | None = None
    entities: list[dict] | None = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("entities", mode="before")
    @classmethod
    def parse_entities(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        if isinstance(v, list):
            return v
        return None


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int
    has_more: bool


class TypingRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=100)


class TypingResponse(BaseModel):
    suggestions: list[str]


class SearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)
    conversation_id: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class SearchResult(BaseModel):
    message_id: str
    conversation_id: str
    conversation_title: str
    content: str
    role: str
    created_at: datetime
    highlight: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    page: int
    page_size: int
