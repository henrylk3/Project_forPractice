from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json
import asyncio
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.api.auth import get_current_user
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationListResponse,
)
from app.schemas.message import (
    ChatRequest,
    ChatResponse,
    MessageResponse,
    MessageListResponse,
    TypingRequest,
    TypingResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services.chat_service import (
    create_conversation,
    get_conversations,
    get_conversation,
    update_conversation,
    delete_conversation,
    get_messages,
    process_chat,
    search_messages,
    mark_messages_read,
    save_message,
)
from app.services.security_service import get_security_service
from app.nlp.dialogue_manager import get_dialogue_manager
from app.nlp.transformer_model import get_chat_model
from app.nlp.llm_client import get_llm_client
from app.utils.helpers import check_rate_limit
from app.config import GENERATION_CONFIG

router = APIRouter(prefix="/chat", tags=["对话"])

SYSTEM_PROMPT = (
    "你是Chatbot，一个智能、友好、乐于助人的AI助手。"
    "你善于理解用户的需求，提供准确、有价值的回答。"
    "回答时条理清晰、语言自然流畅，适当使用分段和要点让回答更易读。"
    "如果用户的问题不明确，主动询问以获取更多信息。"
    "对于复杂问题，给出结构化的分析和建议。"
    "请始终使用中文回复，除非用户明确要求使用其他语言。"
)


def _get_provider() -> str:
    llm_client = get_llm_client()
    if llm_client.is_configured():
        return "api"
    chat_model = get_chat_model()
    if chat_model.is_ready():
        return "local"
    return "fallback"


@router.post("/send", response_model=ChatResponse, summary="发送消息")
async def send_message(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not check_rate_limit(f"chat:{current_user.id}", max_requests=30, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="消息发送过于频繁，请稍后再试",
        )

    security = get_security_service()
    is_valid, error_msg = security.validate_message(chat_request.content)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    sanitized_content = security.sanitize_input(chat_request.content)

    result = await process_chat(
        db=db,
        user=current_user,
        conversation_id=chat_request.conversation_id,
        content=sanitized_content,
        content_type=chat_request.content_type,
        media_url=chat_request.media_url,
        duration=chat_request.duration,
    )

    return ChatResponse(**result)


@router.post("/stream", summary="流式发送消息")
async def stream_message(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not check_rate_limit(f"chat:{current_user.id}", max_requests=30, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="消息发送过于频繁，请稍后再试",
        )

    security = get_security_service()
    is_valid, error_msg = security.validate_message(chat_request.content)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    sanitized_content = security.sanitize_input(chat_request.content)

    if chat_request.conversation_id is None:
        title = sanitized_content[:20] + ("..." if len(sanitized_content) > 20 else "")
        conversation = await create_conversation(db, current_user.id, title)
        conversation_id = conversation.id
    else:
        conversation = await get_conversation(db, chat_request.conversation_id, current_user.id)
        if not conversation:
            conversation = await create_conversation(db, current_user.id)
            conversation_id = conversation.id
        else:
            conversation_id = conversation.id

    user_message = await save_message(
        db, conversation_id, "user", sanitized_content,
        chat_request.content_type, chat_request.media_url,
        chat_request.duration,
    )

    from sqlalchemy import select
    from app.models.message import Message

    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(MAX_HISTORY_TURNS * 2)
    )
    history_messages = list(reversed(history_result.scalars().all()))
    history = [{"role": m.role, "content": m.content} for m in history_messages]

    dialogue_manager = get_dialogue_manager()
    intent_result = dialogue_manager.intent_recognizer.recognize(sanitized_content)
    entities = dialogue_manager.entity_extractor.extract(sanitized_content)

    provider = _get_provider()

    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id, 'message_id': user_message.id, 'provider': provider}, ensure_ascii=False)}\n\n"

        full_response = ""

        try:
            if provider == "api":
                async for token in get_llm_client().chat_stream(sanitized_content, history, SYSTEM_PROMPT):
                    full_response += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0)

            elif provider == "local":
                async for token in _stream_local(sanitized_content, history):
                    full_response += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0)

            else:
                result = await dialogue_manager.process_message(
                    user_input=sanitized_content,
                    history=history,
                )
                full_response = result["content"]
                yield f"data: {json.dumps({'type': 'token', 'content': full_response}, ensure_ascii=False)}\n\n"

        except Exception as e:
            from loguru import logger as log
            log.error(f"Stream generation error (provider={provider}): {e}")

            if not full_response:
                try:
                    result = await dialogue_manager.process_message(
                        user_input=sanitized_content,
                        history=history,
                    )
                    full_response = result["content"]
                except Exception:
                    full_response = _simple_fallback(sanitized_content)

                yield f"data: {json.dumps({'type': 'token', 'content': full_response}, ensure_ascii=False)}\n\n"

        if not full_response.strip():
            full_response = "抱歉，我暂时无法生成回复，请稍后再试。"
            yield f"data: {json.dumps({'type': 'token', 'content': full_response}, ensure_ascii=False)}\n\n"

        bot_message = await save_message(
            db, conversation_id, "assistant", full_response,
            "text", intent=intent_result["intent"], entities=entities,
        )

        yield f"data: {json.dumps({'type': 'done', 'content': full_response, 'message_id': bot_message.id, 'intent': intent_result['intent'], 'provider': provider}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _stream_local(user_input: str, history: list[dict]):
    chat_model = get_chat_model()
    from transformers import TextIteratorStreamer
    import threading

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        for msg in history:
            messages.append(msg)
    messages.append({"role": "user", "content": user_input})

    text = chat_model.tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    input_ids = chat_model.tokenizer.encode(text, return_tensors="pt").to(chat_model.device)

    streamer = TextIteratorStreamer(
        chat_model.tokenizer, skip_prompt=True, skip_special_tokens=True
    )

    generation_kwargs = {
        "input_ids": input_ids,
        "max_new_tokens": GENERATION_CONFIG["max_new_tokens"],
        "temperature": GENERATION_CONFIG["temperature"],
        "top_p": GENERATION_CONFIG["top_p"],
        "top_k": GENERATION_CONFIG["top_k"],
        "do_sample": True,
        "streamer": streamer,
        "pad_token_id": chat_model.tokenizer.eos_token_id,
        "repetition_penalty": GENERATION_CONFIG["repetition_penalty"],
        "no_repeat_ngram_size": 3,
        "use_cache": True,
    }

    thread = threading.Thread(target=chat_model.model.generate, kwargs=generation_kwargs)
    thread.start()

    for new_text in streamer:
        if new_text:
            yield new_text
        await asyncio.sleep(0)

    await asyncio.get_event_loop().run_in_executor(None, thread.join)


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

    return "抱歉，AI服务暂时不可用。请检查后端配置：\n1. 如需使用API模式，请设置环境变量 LLM_API_KEY 和 LLM_API_BASE\n2. 如需使用本地模型，请确保已下载模型文件\n当前使用的是基础回复模式。"


@router.get("/test-llm", summary="测试LLM API连接")
async def test_llm():
    llm_client = get_llm_client()
    chat_model = get_chat_model()

    result = {
        "llm_api_configured": llm_client.is_configured(),
        "local_model_ready": chat_model.is_ready(),
        "provider": _get_provider(),
    }

    if llm_client.is_configured():
        result["api_base"] = llm_client.api_base
        result["model"] = llm_client.model
        try:
            resp = await llm_client.chat("你好", [], SYSTEM_PROMPT)
            result["api_test"] = "success"
            result["api_response"] = resp[:100]
        except Exception as e:
            result["api_test"] = "failed"
            result["api_error"] = str(e)

    return result


@router.get("/conversations", response_model=ConversationListResponse, summary="获取对话列表")
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversations, total = await get_conversations(db, current_user.id, page, page_size)
    return ConversationListResponse(
        conversations=[ConversationResponse.model_validate(c) for c in conversations],
        total=total,
    )


@router.post("/conversations", response_model=ConversationResponse, summary="创建新对话")
async def new_conversation(
    conv_create: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await create_conversation(
        db, current_user.id, conv_create.title
    )
    return ConversationResponse.model_validate(conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse, summary="获取对话详情")
async def get_conv_detail(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await get_conversation(db, conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    return ConversationResponse.model_validate(conversation)


@router.put("/conversations/{conversation_id}", response_model=ConversationResponse, summary="更新对话")
async def update_conv(
    conversation_id: str,
    conv_update: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await update_conversation(
        db, conversation_id, current_user.id,
        **conv_update.model_dump(exclude_unset=True),
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    return ConversationResponse.model_validate(conversation)


@router.delete("/conversations/{conversation_id}", summary="删除对话")
async def delete_conv(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    success = await delete_conversation(db, conversation_id, current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    return {"message": "对话已删除"}


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse, summary="获取消息列表")
async def list_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages, total, has_more = await get_messages(
        db, conversation_id, current_user.id, page, page_size
    )
    return MessageListResponse(
        messages=[MessageResponse.model_validate(m) for m in messages],
        total=total,
        has_more=has_more,
    )


@router.put("/conversations/{conversation_id}/read", summary="标记消息已读")
async def mark_read(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await mark_messages_read(db, conversation_id, current_user.id)
    return {"marked_count": count}


@router.post("/typing", response_model=TypingResponse, summary="输入提示")
async def typing_suggestions(
    typing_request: TypingRequest,
    current_user: User = Depends(get_current_user),
):
    dialogue_manager = get_dialogue_manager()
    suggestions = dialogue_manager.get_typing_suggestions(typing_request.content)
    return TypingResponse(suggestions=suggestions)


@router.post("/search", response_model=SearchResponse, summary="搜索消息")
async def search(
    search_request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results, total = await search_messages(
        db,
        current_user.id,
        search_request.keyword,
        search_request.conversation_id,
        search_request.page,
        search_request.page_size,
    )
    return SearchResponse(
        results=[SearchResult(**r) for r in results],
        total=total,
        page=search_request.page,
        page_size=search_request.page_size,
    )


@router.get("/stats", summary="获取对话统计数据")
async def get_chat_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, func, case
    from app.models.conversation import Conversation as ConvModel
    from app.models.message import Message as MsgModel

    total_conversations = await db.scalar(
        select(func.count()).select_from(ConvModel).where(ConvModel.user_id == current_user.id)
    )

    total_messages = await db.scalar(
        select(func.count())
        .select_from(MsgModel)
        .join(ConvModel, MsgModel.conversation_id == ConvModel.id)
        .where(ConvModel.user_id == current_user.id)
    )

    user_messages = await db.scalar(
        select(func.count())
        .select_from(MsgModel)
        .join(ConvModel, MsgModel.conversation_id == ConvModel.id)
        .where(ConvModel.user_id == current_user.id, MsgModel.role == "user")
    )

    assistant_messages = await db.scalar(
        select(func.count())
        .select_from(MsgModel)
        .join(ConvModel, MsgModel.conversation_id == ConvModel.id)
        .where(ConvModel.user_id == current_user.id, MsgModel.role == "assistant")
    )

    intent_rows = await db.execute(
        select(MsgModel.intent, func.count())
        .join(ConvModel, MsgModel.conversation_id == ConvModel.id)
        .where(ConvModel.user_id == current_user.id, MsgModel.role == "user", MsgModel.intent.isnot(None))
        .group_by(MsgModel.intent)
        .order_by(func.count().desc())
    )
    intent_distribution = {row[0]: row[1] for row in intent_rows.all()}

    content_type_rows = await db.execute(
        select(MsgModel.content_type, func.count())
        .join(ConvModel, MsgModel.conversation_id == ConvModel.id)
        .where(ConvModel.user_id == current_user.id, MsgModel.role == "user")
        .group_by(MsgModel.content_type)
    )
    content_type_distribution = {row[0]: row[1] for row in content_type_rows.all()}

    daily_rows = await db.execute(
        select(func.date(MsgModel.created_at), func.count())
        .join(ConvModel, MsgModel.conversation_id == ConvModel.id)
        .where(ConvModel.user_id == current_user.id)
        .group_by(func.date(MsgModel.created_at))
        .order_by(func.date(MsgModel.created_at).desc())
        .limit(14)
    )
    daily_messages = [{"date": str(row[0]), "count": row[1]} for row in daily_rows.all()]

    return {
        "total_conversations": total_conversations or 0,
        "total_messages": total_messages or 0,
        "user_messages": user_messages or 0,
        "assistant_messages": assistant_messages or 0,
        "intent_distribution": intent_distribution,
        "content_type_distribution": content_type_distribution,
        "daily_messages": daily_messages,
    }


@router.get("/conversations/{conversation_id}/export", summary="导出对话记录")
async def export_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select as sa_select
    from app.models.conversation import Conversation as ConvModel

    conv = await db.scalar(
        sa_select(ConvModel).where(
            ConvModel.id == conversation_id, ConvModel.user_id == current_user.id
        )
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")

    messages, _, _ = await get_messages(db, conversation_id, current_user.id, page=1, page_size=10000)

    lines = [f"对话标题：{conv.title}", f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
    for msg in messages:
        role = "用户" if msg.role == "user" else "AI助手"
        time_str = msg.created_at.strftime("%H:%M:%S") if msg.created_at else ""
        lines.append(f"[{time_str}] {role}：")
        lines.append(msg.content)
        if msg.intent:
            lines.append(f"  (意图: {msg.intent})")
        lines.append("")

    content = "\n".join(lines)

    return {"content": content, "title": conv.title}
