from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import WxLoginRequest, TokenResponse, UserUpdate, UserResponse
from app.services.auth_service import (
    create_access_token,
    verify_token,
    get_wx_openid,
    get_or_create_user,
    is_wx_configured,
)
from app.utils.helpers import check_rate_limit
from app.config import UPLOAD_DIR, SERVER_URL

router = APIRouter(prefix="/auth", tags=["认证"])


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证信息",
        )

    token = auth_header[7:]
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证已过期或无效",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证信息",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已禁用",
        )

    return user


@router.get("/wx-config", summary="检查微信登录配置状态")
async def check_wx_config():
    configured = is_wx_configured()
    return {
        "wx_login_available": configured,
        "message": "微信登录已配置" if configured else "微信登录未配置，请设置WX_APPID和WX_SECRET",
    }


@router.post("/wx-login", response_model=TokenResponse, summary="微信登录")
async def wx_login(request: WxLoginRequest, db: AsyncSession = Depends(get_db)):
    if not check_rate_limit(f"login:{request.code}", max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
        )

    if not is_wx_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="微信登录暂未配置，请先在后端config.py中设置WX_APPID和WX_SECRET，或使用开发模式登录",
        )

    openid, error_msg = await get_wx_openid(request.code)
    if not openid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg or "微信授权失败",
        )

    user = await get_or_create_user(db, openid, request.nickname, request.avatar_url)

    expires_delta = timedelta(days=7)
    expires_at = datetime.now() + expires_delta
    access_token = create_access_token(
        data={"sub": user.id, "openid": user.openid},
        expires_delta=expires_delta,
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        expires_at=expires_at,
    )


@router.post("/dev-login", response_model=TokenResponse, summary="开发环境登录")
async def dev_login(db: AsyncSession = Depends(get_db)):
    dev_openid = "dev_user_001"
    user = await get_or_create_user(db, dev_openid, "开发者", None)

    expires_delta = timedelta(days=30)
    expires_at = datetime.now() + expires_delta
    access_token = create_access_token(
        data={"sub": user.id, "openid": user.openid},
        expires_delta=expires_delta,
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        expires_at=expires_at,
    )


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse, summary="更新用户信息")
async def update_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(current_user, key):
            setattr(current_user, key, value)

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/upload-avatar", summary="上传头像")
async def upload_avatar(
    avatar: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not avatar.content_type or not avatar.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能上传图片文件",
        )

    content = await avatar.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图片大小不能超过5MB",
        )

    ext = avatar.filename.split(".")[-1] if avatar.filename and "." in avatar.filename else "png"
    filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"

    avatar_dir = UPLOAD_DIR / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    file_path = avatar_dir / filename

    with open(file_path, "wb") as f:
        f.write(content)

    avatar_url = f"/uploads/avatars/{filename}"
    full_url = f"{SERVER_URL}{avatar_url}"
    current_user.avatar_url = avatar_url
    await db.commit()
    await db.refresh(current_user)

    return {"url": full_url, "path": avatar_url}
