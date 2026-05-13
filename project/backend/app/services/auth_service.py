import hashlib
import hmac
import httpx
import base64
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, WX_APPID, WX_SECRET
from app.models.user import User


def _hash_password(password: str) -> str:
    salt = base64.b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()[:16])
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return f"pbkdf2_sha256${salt.decode()}${base64.b64encode(hashed).decode()}"


def _verify_password(password: str, hashed: str) -> bool:
    try:
        parts = hashed.split("$")
        if len(parts) != 3 or parts[0] != "pbkdf2_sha256":
            return False
        salt = parts[1].encode()
        stored_hash = base64.b64decode(parts[2])
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return hmac.compare_digest(stored_hash, computed)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def is_wx_configured() -> bool:
    return bool(WX_APPID and WX_SECRET)


async def get_wx_openid(code: str) -> tuple[Optional[str], Optional[str]]:
    if not is_wx_configured():
        return None, "微信小程序未配置AppID和AppSecret，请先在config.py或环境变量中设置WX_APPID和WX_SECRET"

    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": WX_APPID,
        "secret": WX_SECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

            if "openid" in data:
                return data["openid"], None

            errcode = data.get("errcode", -1)
            errmsg = data.get("errmsg", "未知错误")

            error_messages = {
                40029: "微信登录code无效或已过期，请重新获取",
                41002: "AppID缺失，请检查后端配置中的WX_APPID",
                41003: "AppSecret缺失，请检查后端配置中的WX_SECRET",
                40013: "AppID无效，请检查配置是否正确",
                40125: "AppSecret错误，请检查配置是否正确",
                -1: f"微信服务器繁忙，请稍后重试（{errmsg}）",
            }

            detail = error_messages.get(errcode, f"微信授权失败（错误码: {errcode}, {errmsg}）")
            logger.error(f"WeChat auth failed: {data}")
            return None, detail

    except httpx.TimeoutException:
        return None, "微信服务器响应超时，请检查网络连接"
    except Exception as e:
        logger.error(f"WeChat auth request error: {e}")
        return None, f"微信授权请求失败: {str(e)}"


async def get_or_create_user(db: AsyncSession, openid: str, nickname: str = "用户", avatar_url: str | None = None) -> User:
    result = await db.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            openid=openid,
            nickname=nickname,
            avatar_url=avatar_url,
            last_login=datetime.now(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"New user created: {user.id}")
    else:
        user.last_login = datetime.now()
        if nickname and nickname != "用户":
            user.nickname = nickname
        if avatar_url:
            user.avatar_url = avatar_url
        await db.commit()
        await db.refresh(user)

    return user
