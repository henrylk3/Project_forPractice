import os
import uuid
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db
from app.models.user import User
from app.api.auth import get_current_user
from app.config import UPLOAD_DIR, SERVER_URL

router = APIRouter(prefix="/voice", tags=["语音"])

_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            try:
                import imageio_ffmpeg
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                ffmpeg_dir = str(Path(ffmpeg_exe).parent)
                current_path = os.environ.get("PATH", "")
                if ffmpeg_dir not in current_path:
                    os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path

                ffmpeg_copy = Path(ffmpeg_dir) / "ffmpeg.exe"
                if not ffmpeg_copy.exists():
                    import shutil
                    shutil.copy2(ffmpeg_exe, str(ffmpeg_copy))

                _original_load_audio = whisper.audio.load_audio
                def _patched_load_audio(file, sr=whisper.audio.SAMPLE_RATE):
                    cmd = [
                        str(ffmpeg_copy),
                        "-nostdin",
                        "-threads", "0",
                        "-i", file,
                        "-f", "s16le",
                        "-ac", "1",
                        "-acodec", "pcm_s16le",
                        "-ar", str(sr),
                        "-"
                    ]
                    from subprocess import run, CalledProcessError
                    try:
                        out = run(cmd, capture_output=True, check=True).stdout
                    except CalledProcessError as e:
                        raise RuntimeError(f"Failed to load audio: {e.stderr.decode()}") from e
                    import numpy as np
                    return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0

                whisper.audio.load_audio = _patched_load_audio
                logger.info(f"Using ffmpeg from imageio-ffmpeg: {ffmpeg_exe}")
            except Exception as e:
                logger.warning(f"imageio-ffmpeg not available: {e}")
            _whisper_model = whisper.load_model("base")
            logger.info("Whisper model loaded successfully")
        except ImportError:
            logger.warning("whisper not installed, speech recognition will use fallback")
            _whisper_model = False
        except Exception as e:
            logger.error(f"Failed to load whisper model: {e}")
            _whisper_model = False
    return _whisper_model if _whisper_model is not False else None


@router.post("/recognize", summary="语音识别")
async def recognize_speech(
    audio: UploadFile = File(...),
    language: str = Query("zh", description="语言代码，如zh/en"),
    current_user: User = Depends(get_current_user),
):
    if audio.content_type and not audio.content_type.startswith(("audio/", "video/", "application/octet-stream")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请上传音频文件",
        )

    content = await audio.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="音频文件不能超过10MB",
        )

    if len(content) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="音频文件过短，请重新录制",
        )

    whisper_model = _get_whisper_model()

    if whisper_model is None:
        return await _fallback_recognize(content, audio.filename)

    tmp_path = None
    try:
        ext = ".mp3"
        if audio.filename and "." in audio.filename:
            ext = Path(audio.filename).suffix or ".mp3"

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        result = whisper_model.transcribe(tmp_path, language="zh" if language.startswith("zh") else language)
        text = result.get("text", "").strip()

        if tmp_path and Path(tmp_path).exists():
            os.unlink(tmp_path)
            tmp_path = None

        if not text:
            return {
                "text": "",
                "confidence": 0.0,
                "success": False,
                "message": "未能识别语音内容，请重新录制",
            }

        segments = result.get("segments", [])
        confidence = sum(s.get("avg_logprob", 0) for s in segments) / max(len(segments), 1)
        confidence_score = min(max((confidence + 1) * 50, 0), 100)

        return {
            "text": text,
            "confidence": round(confidence_score, 1),
            "success": True,
            "language": result.get("language", language),
        }

    except Exception as e:
        logger.error(f"Speech recognition error: {e}")
        if tmp_path and Path(tmp_path).exists():
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        return await _fallback_recognize(content, audio.filename)


async def _fallback_recognize(content: bytes, filename: str | None) -> dict:
    return {
        "text": "",
        "confidence": 0.0,
        "success": False,
        "message": "语音识别服务暂不可用，请使用文字输入",
    }


@router.post("/synthesize", summary="语音合成")
async def synthesize_speech(
    text: str = Query(..., min_length=1, max_length=500, description="要合成的文本"),
    speed: float = Query(1.0, ge=0.5, le=2.0, description="语速，0.5-2.0"),
    volume: float = Query(1.0, ge=0.1, le=2.0, description="音量，0.1-2.0"),
    voice: str = Query("default", description="音色选择"),
    current_user: User = Depends(get_current_user),
):
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文本内容不能为空",
        )

    try:
        audio_path = await _generate_tts(text, speed, volume, voice, current_user.id)
        if audio_path:
            return {"audio_url": audio_path, "success": True}
    except Exception as e:
        logger.error(f"TTS error: {e}")

    return {
        "audio_url": None,
        "success": False,
        "message": "语音合成服务暂不可用",
    }


async def _generate_tts(text: str, speed: float, volume: float, voice: str, user_id: str) -> Optional[str]:
    try:
        import edge_tts

        voice_map = {
            "default": "zh-CN-XiaoxiaoNeural",
            "male": "zh-CN-YunxiNeural",
            "female": "zh-CN-XiaoyiNeural",
            "gentle": "zh-CN-XiaohanNeural",
        }

        selected_voice = voice_map.get(voice, voice_map["default"])

        tts_dir = UPLOAD_DIR / "tts"
        tts_dir.mkdir(parents=True, exist_ok=True)

        filename = f"tts_{user_id}_{uuid.uuid4().hex[:8]}.mp3"
        output_path = tts_dir / filename

        rate = f"{'+'
                      if speed > 1 else ''}{int((speed - 1) * 100)}%"
        volume_str = f"{'+'
                               if volume > 1 else ''}{int((volume - 1) * 100)}%"

        communicate = edge_tts.Communicate(text, selected_voice, rate=rate, volume=volume_str)
        await communicate.save(str(output_path))

        return f"/uploads/tts/{filename}"

    except ImportError:
        logger.warning("edge_tts not installed, TTS not available")
        return None
    except Exception as e:
        logger.error(f"edge_tts generation error: {e}")
        return None


@router.get("/voices", summary="获取可用音色列表")
async def get_voices():
    return {
        "voices": [
            {"id": "default", "name": "小晓（默认女声）", "description": "温柔自然的女声", "icon": "👩"},
            {"id": "male", "name": "云希（男声）", "description": "沉稳大气的男声", "icon": "👨"},
            {"id": "female", "name": "小依（女声）", "description": "甜美活泼的女声", "icon": "👧"},
            {"id": "gentle", "name": "小涵（温柔女声）", "description": "温柔知性的女声", "icon": "👩‍🏫"},
        ]
    }


@router.post("/upload-image", summary="上传图片")
async def upload_image(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能上传图片文件",
        )

    content = await image.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图片大小不能超过10MB",
        )

    ext = image.filename.split(".")[-1] if image.filename and "." in image.filename else "jpg"
    filename = f"img_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"

    img_dir = UPLOAD_DIR / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    file_path = img_dir / filename

    with open(file_path, "wb") as f:
        f.write(content)

    path = f"/uploads/images/{filename}"
    full_url = f"{SERVER_URL}{path}"
    return {"path": path, "url": full_url}


@router.post("/upload-audio", summary="上传语音文件")
async def upload_audio(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not audio.content_type or not (
        audio.content_type.startswith("audio/")
        or (audio.filename and audio.filename.endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg", ".silk")))
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能上传音频文件",
        )

    content = await audio.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="音频大小不能超过20MB",
        )

    ext = "mp3"
    if audio.filename and "." in audio.filename:
        ext = audio.filename.rsplit(".", 1)[-1]
    filename = f"audio_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"

    audio_dir = UPLOAD_DIR / "audios"
    audio_dir.mkdir(parents=True, exist_ok=True)
    file_path = audio_dir / filename

    with open(file_path, "wb") as f:
        f.write(content)

    path = f"/uploads/audios/{filename}"
    full_url = f"{SERVER_URL}{path}"
    return {"path": path, "url": full_url}
