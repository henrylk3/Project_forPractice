from datetime import datetime

from pydantic import BaseModel, Field


class WxLoginRequest(BaseModel):
    code: str = Field(..., description="微信登录code")
    nickname: str | None = Field(None, max_length=64)
    avatar_url: str | None = Field(None, max_length=512)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    nickname: str
    avatar_url: str | None = None
    expires_at: datetime


class UserBase(BaseModel):
    nickname: str = Field(default="用户", max_length=64)
    avatar_url: str | None = None
    phone: str | None = None


class UserUpdate(UserBase):
    bot_role: str | None = Field(None, pattern="^(assistant|tutor|companion|creative)$")
    dialogue_style: str | None = Field(None, pattern="^(friendly|formal|humorous|concise)$")
    language: str | None = None


class UserResponse(UserBase):
    id: str
    openid: str
    is_active: bool
    bot_role: str
    dialogue_style: str
    language: str
    created_at: datetime
    last_login: datetime | None = None

    model_config = {"from_attributes": True}
