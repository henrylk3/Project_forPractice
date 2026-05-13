from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(None, max_length=128)


class ConversationUpdate(BaseModel):
    title: str | None = Field(None, max_length=128)
    is_pinned: bool | None = None


class ConversationResponse(BaseModel):
    id: str
    title: str
    is_pinned: bool
    message_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    total: int
