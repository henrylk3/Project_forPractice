import json
import base64
import asyncio
from typing import Optional, AsyncGenerator
from pathlib import Path

import httpx
from loguru import logger

from app.config import (
    LLM_API_KEY, LLM_API_BASE, LLM_MODEL, LLM_VISION_MODEL,
    VISION_API_KEY, VISION_API_BASE, VISION_MODEL,
    MAX_HISTORY_TURNS, GENERATION_CONFIG,
)

SYSTEM_PROMPT = (
    "你是Chatbot，一个智能、友好、乐于助人的AI助手。"
    "你善于理解用户的需求，提供准确、有价值的回答。"
    "回答时条理清晰、语言自然流畅，适当使用分段和要点让回答更易读。"
    "如果用户的问题不明确，主动询问以获取更多信息。"
    "对于复杂问题，给出结构化的分析和建议。"
    "请始终使用中文回复，除非用户明确要求使用其他语言。"
)


class LLMApiClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.api_key = LLM_API_KEY.strip().rstrip(",").strip()
        self.api_base = LLM_API_BASE.strip().rstrip(",").strip().rstrip("/")
        self.model = LLM_MODEL.strip().rstrip(",").strip()
        self.vision_model = LLM_VISION_MODEL.strip().rstrip(",").strip() or self.model

        self.vision_api_key = VISION_API_KEY.strip().rstrip(",").strip() or self.api_key
        self.vision_api_base = VISION_API_BASE.strip().rstrip(",").strip().rstrip("/")
        self.vision_model_name = VISION_MODEL.strip().rstrip(",").strip() or self.vision_model

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        )
        logger.info(
            f"LLMApiClient initialized: base={self.api_base}, model={self.model}, "
            f"vision_base={self.vision_api_base}, vision_model={self.vision_model_name}"
        )

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def is_vision_configured(self) -> bool:
        return bool(self.vision_api_key)

    def _build_messages(
        self,
        user_input: str,
        history: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> list[dict]:
        messages = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT}]

        if history:
            recent = history[-(MAX_HISTORY_TURNS * 2):]
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_input})
        return messages

    async def chat(
        self,
        user_input: str,
        history: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        if not self.is_configured():
            raise ValueError("LLM API key not configured")

        messages = self._build_messages(user_input, history, system_prompt)

        try:
            resp = await self.client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": GENERATION_CONFIG["max_new_tokens"],
                    "temperature": GENERATION_CONFIG["temperature"],
                    "top_p": GENERATION_CONFIG["top_p"],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip() if content else "抱歉，我暂时无法生成回复。"

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            raise

    async def chat_with_image(
        self,
        user_input: str,
        image_base64: str,
        image_media_type: str = "image/jpeg",
        history: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        if not self.is_vision_configured():
            return "图片识别功能未配置。请在环境变量中设置 VISION_API_KEY（通义千问 DashScope API Key）以启用图片识别。"

        vision_model = self.vision_model_name
        vision_api_key = self.vision_api_key
        vision_api_base = self.vision_api_base

        logger.info(f"Vision API request: model={vision_model}, base={vision_api_base}")

        messages = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT}]

        if history:
            recent = history[-(MAX_HISTORY_TURNS * 2):]
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        user_message = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_media_type};base64,{image_base64}"
                    },
                },
                {
                    "type": "text",
                    "text": user_input or "请描述这张图片的内容",
                },
            ],
        }
        messages.append(user_message)

        try:
            resp = await self.client.post(
                f"{vision_api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {vision_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": vision_model,
                    "messages": messages,
                    "max_tokens": GENERATION_CONFIG["max_new_tokens"],
                    "temperature": GENERATION_CONFIG["temperature"],
                    "top_p": GENERATION_CONFIG["top_p"],
                    "stream": False,
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip() if content else "抱歉，我无法识别这张图片。"

        except httpx.HTTPStatusError as e:
            error_text = e.response.text if e.response else ""
            status_code = e.response.status_code if e.response else 0
            logger.error(f"LLM Vision API HTTP error: {status_code} - {error_text}")
            if status_code == 400:
                return f"图片识别请求格式错误，请检查视觉模型配置。错误详情：{error_text[:200]}"
            raise
        except Exception as e:
            logger.error(f"LLM Vision API error: {e}")
            raise

    async def chat_stream(
        self,
        user_input: str,
        history: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        if not self.is_configured():
            raise ValueError("LLM API key not configured")

        messages = self._build_messages(user_input, history, system_prompt)

        try:
            async with self.client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": GENERATION_CONFIG["max_new_tokens"],
                    "temperature": GENERATION_CONFIG["temperature"],
                    "top_p": GENERATION_CONFIG["top_p"],
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API stream HTTP error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"LLM API stream error: {e}")
            raise


_llm_client: Optional[LLMApiClient] = None


def get_llm_client() -> LLMApiClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMApiClient()
    return _llm_client
