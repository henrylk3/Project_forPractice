import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/chatbot.db")

SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
SERVER_URL = os.getenv("SERVER_URL", f"http://localhost:{SERVER_PORT}")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "api")

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL", "deepseek-v4-pro")

VISION_API_KEY = os.getenv("VISION_API_KEY", "")
VISION_API_BASE = os.getenv("VISION_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen-vl-plus")

MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen-1_8B-Chat")
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", str(BASE_DIR / "model_cache"))
MAX_CONTEXT_LENGTH = int(os.getenv("MAX_CONTEXT_LENGTH", "2048"))
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "8"))
PRELOAD_MODEL = os.getenv("PRELOAD_MODEL", "false").lower() == "true"

INTENT_MODEL_PATH = os.getenv("INTENT_MODEL_PATH", str(BASE_DIR / "models" / "intent"))
ENTITY_MODEL_PATH = os.getenv("ENTITY_MODEL_PATH", str(BASE_DIR / "models" / "entity"))

CORS_ORIGINS = [
    "https://servicewechat.com",
    "http://localhost:3000",
    "http://localhost:8080",
]

WX_APPID = os.getenv("WX_APPID", "wx225606b66973973c")
WX_SECRET = os.getenv("WX_SECRET", "15578d8e0eebd2859f3423629f59b2b6")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "app.log"))

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_MESSAGE_LENGTH = 2000
RATE_LIMIT_PER_MINUTE = 30

GENERATION_CONFIG = {
    "max_new_tokens": int(os.getenv("GEN_MAX_TOKENS", "512")),
    "temperature": float(os.getenv("GEN_TEMPERATURE", "0.7")),
    "top_p": float(os.getenv("GEN_TOP_P", "0.9")),
    "top_k": int(os.getenv("GEN_TOP_K", "50")),
    "repetition_penalty": float(os.getenv("GEN_REP_PENALTY", "1.15")),
}
