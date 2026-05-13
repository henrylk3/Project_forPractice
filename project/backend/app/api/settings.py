from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.api.auth import get_current_user

router = APIRouter(prefix="/settings", tags=["设置"])

BOT_ROLES = {
    "assistant": {"name": "智能助手", "description": "乐于帮助用户解决问题", "icon": "🤖"},
    "tutor": {"name": "耐心老师", "description": "善于用简单易懂的方式解释概念", "icon": "👨‍🏫"},
    "companion": {"name": "友好伙伴", "description": "善于倾听和陪伴用户", "icon": "🤝"},
    "creative": {"name": "创意达人", "description": "善于提供新颖的想法和灵感", "icon": "💡"},
}

DIALOGUE_STYLES = {
    "friendly": {"name": "亲切友好", "description": "温暖亲切的交流方式", "icon": "😊"},
    "formal": {"name": "正式专业", "description": "严谨专业的表达方式", "icon": "👔"},
    "humorous": {"name": "幽默风趣", "description": "轻松愉快的聊天风格", "icon": "😄"},
    "concise": {"name": "简洁精炼", "description": "直奔主题的沟通方式", "icon": "⚡"},
}

FAQ_ITEMS = [
    {
        "id": "faq_1",
        "question": "如何开始对话？",
        "answer": "在聊天界面输入你想问的问题，点击发送按钮即可开始对话。你可以问我任何问题，我会尽力帮助你。",
    },
    {
        "id": "faq_2",
        "question": "如何切换机器人角色？",
        "answer": "进入设置页面，在「机器人角色」选项中选择你喜欢的角色。不同的角色有不同的对话风格和专业领域。",
    },
    {
        "id": "faq_3",
        "question": "如何查看历史对话？",
        "answer": "在聊天页面点击左上角的菜单按钮，可以查看所有历史对话记录。你也可以使用搜索功能快速找到特定内容。",
    },
    {
        "id": "faq_4",
        "question": "我的对话数据安全吗？",
        "answer": "我们非常重视用户数据安全。所有对话数据都经过加密存储，不会分享给第三方。你可以随时删除对话记录。",
    },
    {
        "id": "faq_5",
        "question": "如何调整对话风格？",
        "answer": "进入设置页面，在「对话风格」选项中选择你喜欢的风格。支持亲切友好、正式专业、幽默风趣、简洁精炼四种风格。",
    },
    {
        "id": "faq_6",
        "question": "支持哪些消息类型？",
        "answer": "目前支持文本消息、表情消息和图片消息。我们正在开发更多消息类型的支持。",
    },
]


@router.get("/bot-roles", summary="获取机器人角色列表")
async def get_bot_roles():
    return {"roles": BOT_ROLES}


@router.get("/dialogue-styles", summary="获取对话风格列表")
async def get_dialogue_styles():
    return {"styles": DIALOGUE_STYLES}


@router.get("/faq", summary="获取常见问题")
async def get_faq():
    return {"items": FAQ_ITEMS}


@router.get("/help", summary="获取帮助信息")
async def get_help():
    help_items = [
        {"title": "快速入门", "content": "输入问题即可开始对话，支持多轮上下文理解"},
        {"title": "消息类型", "content": "支持文字、表情、图片等多种消息类型"},
        {"title": "对话管理", "content": "可以创建多个对话，支持搜索和删除"},
        {"title": "个性化设置", "content": "可自定义机器人角色和对话风格"},
        {"title": "数据安全", "content": "对话数据加密存储，可随时删除"},
    ]
    return {"items": help_items}


@router.put("/bot-role", summary="设置机器人角色")
async def set_bot_role(
    role: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if role not in BOT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的角色类型，可选: {list(BOT_ROLES.keys())}",
        )
    current_user.bot_role = role
    await db.commit()
    await db.refresh(current_user)
    return {"message": "角色已更新", "role": role, "info": BOT_ROLES[role]}


@router.put("/dialogue-style", summary="设置对话风格")
async def set_dialogue_style(
    style: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if style not in DIALOGUE_STYLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的对话风格，可选: {list(DIALOGUE_STYLES.keys())}",
        )
    current_user.dialogue_style = style
    await db.commit()
    await db.refresh(current_user)
    return {"message": "风格已更新", "style": style, "info": DIALOGUE_STYLES[style]}
