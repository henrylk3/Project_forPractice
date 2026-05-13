import httpx
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.config import WX_APPID, WX_SECRET, UPLOAD_DIR

router = APIRouter(prefix="/qrcode", tags=["二维码"])


async def _get_access_token() -> str:
    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": WX_APPID,
        "secret": WX_SECRET,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if "access_token" not in data:
        raise HTTPException(status_code=500, detail=f"获取access_token失败: {data.get('errmsg', '未知错误')}")

    return data["access_token"]


@router.get("/wxacode")
async def get_wxacode(path: str = "pages/login/login", width: int = 430):
    access_token = await _get_access_token()

    url = f"https://api.weixin.qq.com/wxa/getwxacode?access_token={access_token}"

    body = {
        "path": path,
        "width": width,
        "auto_color": False,
        "line_color": {"r": 74, "g": 144, "b": 217},
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=body)
        content_type = resp.headers.get("content-type", "")

    if "image" in content_type:
        qrcode_dir = UPLOAD_DIR / "qrcodes"
        qrcode_dir.mkdir(parents=True, exist_ok=True)
        qrcode_path = qrcode_dir / "wxacode.png"
        qrcode_path.write_bytes(resp.content)

        return Response(
            content=resp.content,
            media_type="image/png",
            headers={"Content-Disposition": "inline; filename=wxacode.png"},
        )
    else:
        error_data = resp.json()
        raise HTTPException(
            status_code=500,
            detail=f"生成小程序码失败: {error_data.get('errmsg', '未知错误')} (errcode: {error_data.get('errcode')})",
        )


@router.get("/wxacode-unlimit")
async def get_wxacode_unlimit(scene: str = "index", page: str = "pages/login/login", width: int = 430):
    access_token = await _get_access_token()

    url = f"https://api.weixin.qq.com/wxa/getwxacodeunlimit?access_token={access_token}"

    body = {
        "scene": scene,
        "page": page,
        "width": width,
        "auto_color": False,
        "line_color": {"r": 74, "g": 144, "b": 217},
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=body)
        content_type = resp.headers.get("content-type", "")

    if "image" in content_type:
        qrcode_dir = UPLOAD_DIR / "qrcodes"
        qrcode_dir.mkdir(parents=True, exist_ok=True)
        qrcode_path = qrcode_dir / "wxacode_unlimit.png"
        qrcode_path.write_bytes(resp.content)

        return Response(
            content=resp.content,
            media_type="image/png",
            headers={"Content-Disposition": "inline; filename=wxacode_unlimit.png"},
        )
    else:
        error_data = resp.json()
        raise HTTPException(
            status_code=500,
            detail=f"生成小程序码失败: {error_data.get('errmsg', '未知错误')} (errcode: {error_data.get('errcode')})",
        )
