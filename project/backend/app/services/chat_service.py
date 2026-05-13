import json
import uuid
import base64
from datetime import datetime
from typing import Optional
from pathlib import Path

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.nlp.dialogue_manager import get_dialogue_manager
from app.nlp.llm_client import get_llm_client
from app.nlp.transformer_model import get_chat_model
from app.config import MAX_HISTORY_TURNS, UPLOAD_DIR


SYSTEM_PROMPT_TEMPLATE = (
    "你是Chatbot，一个智能、友好、乐于助人的AI助手。"
    "你善于理解用户的需求，提供准确、有价值的回答。"
    "回答时条理清晰、语言自然流畅，适当使用分段和要点让回答更易读。"
    "如果用户的问题不明确，主动询问以获取更多信息。"
    "对于复杂问题，给出结构化的分析和建议。"
    "请始终使用中文回复，除非用户明确要求使用其他语言。"
    "\n\n当前时间：{current_time}"
)


def _get_system_prompt() -> str:
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    time_str = now.strftime(f"%Y年%m月%d日 {weekdays[now.weekday()]} %H:%M")
    return SYSTEM_PROMPT_TEMPLATE.format(current_time=time_str)


async def create_conversation(db: AsyncSession, user_id: str, title: str | None = None) -> Conversation:
    conversation = Conversation(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=title or "新对话",
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_conversations(
    db: AsyncSession, user_id: str, page: int = 1, page_size: int = 20
) -> tuple[list[Conversation], int]:
    count_result = await db.execute(
        select(func.count()).where(Conversation.user_id == user_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.is_pinned.desc(), Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    conversations = list(result.scalars().all())
    return conversations, total


async def get_conversation(db: AsyncSession, conversation_id: str, user_id: str) -> Optional[Conversation]:
    result = await db.execute(
        select(Conversation).where(
            and_(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def update_conversation(
    db: AsyncSession, conversation_id: str, user_id: str, **kwargs
) -> Optional[Conversation]:
    conversation = await get_conversation(db, conversation_id, user_id)
    if not conversation:
        return None

    for key, value in kwargs.items():
        if value is not None and hasattr(conversation, key):
            setattr(conversation, key, value)

    await db.commit()
    await db.refresh(conversation)
    return conversation


async def delete_conversation(db: AsyncSession, conversation_id: str, user_id: str) -> bool:
    conversation = await get_conversation(db, conversation_id, user_id)
    if not conversation:
        return False

    await db.delete(conversation)
    await db.commit()
    return True


async def get_messages(
    db: AsyncSession,
    conversation_id: str,
    user_id: str,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Message], int, bool]:
    conversation = await get_conversation(db, conversation_id, user_id)
    if not conversation:
        return [], 0, False

    count_result = await db.execute(
        select(func.count()).where(Message.conversation_id == conversation_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
    )
    messages = list(result.scalars().all())
    has_more = len(messages) > page_size
    messages = messages[:page_size]

    return messages, total, has_more


async def save_message(
    db: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    content_type: str = "text",
    media_url: str | None = None,
    duration: int | None = None,
    intent: str | None = None,
    entities: list | None = None,
) -> Message:
    message = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=role,
        content=content,
        content_type=content_type,
        media_url=media_url,
        duration=duration,
        intent=intent,
        entities=json.dumps(entities, ensure_ascii=False) if entities else None,
    )
    db.add(message)

    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if conv:
        conv.message_count += 1
        conv.updated_at = datetime.now()

    await db.commit()
    await db.refresh(message)
    return message


def _get_provider() -> str:
    llm_client = get_llm_client()
    if llm_client.is_configured():
        return "api"
    chat_model = get_chat_model()
    if chat_model.is_ready():
        return "local"
    return "fallback"


def _simple_fallback(user_input: str) -> str:
    input_lower = user_input.lower()

    if any(w in input_lower for w in ["你好", "hello", "hi", "嗨", "hey"]):
        return "你好！我是Chatbot，很高兴见到你！有什么我可以帮助你的吗？"
    if any(w in input_lower for w in ["再见", "拜拜", "bye"]):
        return "再见！期待下次和你聊天，祝你一切顺利！"
    if any(w in input_lower for w in ["谢谢", "感谢", "thank"]):
        return "不客气！能帮到你是我的荣幸，如果还有其他问题随时问我。"
    if any(w in input_lower for w in ["你是谁", "你叫什么", "你是什么"]):
        return "我是Chatbot，一个智能AI助手。我可以回答问题、提供建议、帮你分析问题，随时为你服务！"
    if any(w in input_lower for w in ["能做什么", "你会什么", "功能"]):
        return "我可以帮你：\n1. 回答各种问题\n2. 提供建议和思路\n3. 解释复杂概念\n4. 进行日常对话\n5. 帮你分析和整理信息\n有什么想聊的尽管说！"

    return "抱歉，AI服务暂时不可用，请检查后端LLM_API_KEY配置。"


async def _generate_response(content: str, history: list[dict]) -> str:
    provider = _get_provider()

    if provider == "api":
        try:
            llm_client = get_llm_client()
            response = await llm_client.chat(content, history, _get_system_prompt())
            return response
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            try:
                dialogue_manager = get_dialogue_manager()
                result = await dialogue_manager.process_message(user_input=content, history=history)
                return result["content"]
            except Exception:
                return _simple_fallback(content)

    elif provider == "local":
        try:
            chat_model = get_chat_model()
            response = chat_model.generate_response(content, history, _get_system_prompt())
            return response
        except Exception as e:
            logger.error(f"Local model error: {e}")
            return _simple_fallback(content)

    else:
        try:
            dialogue_manager = get_dialogue_manager()
            result = await dialogue_manager.process_message(user_input=content, history=history)
            return result["content"]
        except Exception:
            return _simple_fallback(content)


async def _generate_image_response(content: str, media_url: str, history: list[dict]) -> str:
    try:
        image_path = media_url
        if media_url.startswith("http://") or media_url.startswith("https://"):
            from urllib.parse import urlparse
            parsed = urlparse(media_url)
            image_path = str(UPLOAD_DIR / parsed.path.lstrip("/uploads/").lstrip("/"))
        elif media_url.startswith("/uploads/"):
            image_path = str(UPLOAD_DIR / media_url.replace("/uploads/", ""))

        if not Path(image_path).exists():
            return "抱歉，图片文件不存在，无法识别。"

        ext = Path(image_path).suffix.lower()
        media_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        image_media_type = media_type_map.get(ext, "image/jpeg")

        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")

        llm_client = get_llm_client()
        if llm_client.is_configured():
            user_text = content if content and content != "[图片]" else ""
            response = await llm_client.chat_with_image(
                user_text, image_base64, image_media_type, history, _get_system_prompt()
            )
            return response
        else:
            return "抱歉，图片识别功能需要配置LLM API才能使用。请在后端配置LLM_API_KEY。"

    except Exception as e:
        logger.error(f"Image recognition error: {e}")
        return f"图片识别失败：{str(e)}"


async def process_chat(
    db: AsyncSession,
    user: User,
    conversation_id: str | None,
    content: str,
    content_type: str = "text",
    media_url: str | None = None,
    duration: int | None = None,
) -> dict:
    if conversation_id is None:
        title = content[:20] + ("..." if len(content) > 20 else "")
        conversation = await create_conversation(db, user.id, title)
        conversation_id = conversation.id
    else:
        conversation = await get_conversation(db, conversation_id, user.id)
        if not conversation:
            conversation = await create_conversation(db, user.id)
            conversation_id = conversation.id

    logger.info(f"process_chat: content_type={content_type}, media_url={media_url}, duration={duration}")

    user_message = await save_message(
        db, conversation_id, "user", content, content_type, media_url, duration
    )

    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(MAX_HISTORY_TURNS * 2)
    )
    history_messages = list(reversed(history_result.scalars().all()))
    history = [{"role": m.role, "content": m.content} for m in history_messages]

    if content_type == "image" and media_url:
        response_content = await _generate_image_response(content, media_url, history)
    else:
        response_content = await _generate_response(content, history)

    dialogue_manager = get_dialogue_manager()
    intent_result = dialogue_manager.intent_recognizer.recognize(content)
    entities = dialogue_manager.entity_extractor.extract(content)

    bot_message = await save_message(
        db,
        conversation_id,
        "assistant",
        response_content,
        "text",
        intent=intent_result["intent"],
        entities=entities,
    )

    return {
        "conversation_id": conversation_id,
        "message_id": bot_message.id,
        "role": "assistant",
        "content": response_content,
        "content_type": "text",
        "intent": intent_result["intent"],
        "entities": entities,
        "created_at": bot_message.created_at,
    }


async def search_messages(
    db: AsyncSession,
    user_id: str,
    keyword: str,
    conversation_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    conditions = [
        Conversation.user_id == user_id,
        Message.content.contains(keyword),
    ]
    if conversation_id:
        conditions.append(Message.conversation_id == conversation_id)

    query = (
        select(Message, Conversation.title.label("conversation_title"))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(and_(*conditions))
    )

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        query.order_by(Message.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    results = []
    for row in result:
        msg, conv_title = row
        idx = msg.content.lower().find(keyword.lower())
        start = max(0, idx - 20)
        end = min(len(msg.content), idx + len(keyword) + 20)
        highlight = msg.content[start:end]
        if start > 0:
            highlight = "..." + highlight
        if end < len(msg.content):
            highlight = highlight + "..."

        results.append({
            "message_id": msg.id,
            "conversation_id": msg.conversation_id,
            "conversation_title": conv_title,
            "content": msg.content,
            "role": msg.role,
            "created_at": msg.created_at,
            "highlight": highlight,
        })

    return results, total


async def mark_messages_read(db: AsyncSession, conversation_id: str, user_id: str) -> int:
    conversation = await get_conversation(db, conversation_id, user_id)
    if not conversation:
        return 0

    result = await db.execute(
        select(Message)
        .where(
            and_(
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
                Message.is_read == False,
            )
        )
    )
    messages = list(result.scalars().all())
    count = 0
    for msg in messages:
        msg.is_read = True
        count += 1

    await db.commit()
    return count
