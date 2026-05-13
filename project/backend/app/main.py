import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config import CORS_ORIGINS, LOG_LEVEL, LOG_FILE, UPLOAD_DIR, PRELOAD_MODEL
from app.database import init_db
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.settings import router as settings_router
from app.api.voice import router as voice_router
from app.api.qrcode import router as qrcode_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_dir = Path(LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(LOG_FILE, rotation="10 MB", retention="7 days", level=LOG_LEVEL)
    logger.info("Starting ChatBot API Server...")

    await init_db()
    logger.info("Database initialized")

    from app.nlp.llm_client import get_llm_client
    llm_client = get_llm_client()
    if llm_client.is_configured():
        logger.info(f"LLM API mode: base={llm_client.api_base}, model={llm_client.model}")
    else:
        logger.warning("LLM API key not configured. Set LLM_API_KEY environment variable to enable API mode.")

    if PRELOAD_MODEL:
        import threading
        from app.nlp.transformer_model import get_chat_model

        def preload_model():
            try:
                model = get_chat_model()
                model.preload()
                logger.info("Local model preloaded successfully")
            except Exception as e:
                logger.warning(f"Local model preload failed: {e}")

        preload_thread = threading.Thread(target=preload_model, daemon=True)
        preload_thread.start()

    yield

    logger.info("Shutting down ChatBot API Server...")

    try:
        from app.nlp.llm_client import get_llm_client
        llm_client = get_llm_client()
        await llm_client.client.aclose()
        logger.info("LLM API client closed")
    except Exception as e:
        logger.warning(f"Error closing LLM client: {e}")


app = FastAPI(
    title="Chatbot API",
    description="智能聊天机器人后端服务",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")
app.include_router(qrcode_router, prefix="/api/v1")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/", summary="健康检查")
async def root():
    from app.nlp.llm_client import get_llm_client
    from app.nlp.transformer_model import get_chat_model

    llm_client = get_llm_client()
    chat_model = get_chat_model()

    if llm_client.is_configured():
        provider = "api"
    elif chat_model.is_ready():
        provider = "local"
    else:
        provider = "fallback"

    return {
        "service": "Chatbot API",
        "version": "1.0.0",
        "status": "running",
        "provider": provider,
    }


@app.get("/health", summary="健康检查详情")
async def health_check():
    from app.nlp.llm_client import get_llm_client
    from app.nlp.transformer_model import get_chat_model

    llm_client = get_llm_client()
    chat_model = get_chat_model()

    return {
        "status": "healthy",
        "version": "1.0.0",
        "services": {
            "api": "running",
            "database": "connected",
            "llm_api": "configured" if llm_client.is_configured() else "not_configured",
            "local_model": "loaded" if chat_model.is_ready() else "not_loaded",
        },
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "服务器内部错误，请稍后重试"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
