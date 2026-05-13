import json
import threading
from pathlib import Path
from typing import Optional

from loguru import logger

from app.config import MODEL_NAME, MODEL_CACHE_DIR, MAX_CONTEXT_LENGTH, MAX_HISTORY_TURNS


class TransformerChatModel:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.model = None
        self.tokenizer = None
        self.device = None
        self._model_loaded = False
        self._loading = False

    def _load_model(self):
        if self._model_loaded:
            return
        if self._loading:
            return
        self._loading = True

        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM

            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            cache_dir = Path(MODEL_CACHE_DIR)
            cache_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Loading model {MODEL_NAME} on {self.device}...")

            self.tokenizer = AutoTokenizer.from_pretrained(
                MODEL_NAME,
                cache_dir=str(cache_dir),
                trust_remote_code=True,
                use_fast=True,
            )

            if self.device.type == "cuda":
                self.model = AutoModelForCausalLM.from_pretrained(
                    MODEL_NAME,
                    cache_dir=str(cache_dir),
                    torch_dtype=torch.float16,
                    device_map="auto",
                    trust_remote_code=True,
                )
            else:
                self.model = AutoModelForCausalLM.from_pretrained(
                    MODEL_NAME,
                    cache_dir=str(cache_dir),
                    torch_dtype=torch.float32,
                    trust_remote_code=True,
                    low_cpu_mem_usage=True,
                )
                self.model = self.model.to(self.device)

            self.model.eval()

            if hasattr(self.model, 'gradient_checkpointing_disable'):
                self.model.gradient_checkpointing_disable()

            self._model_loaded = True
            self._loading = False
            logger.info(f"Model loaded successfully on {self.device}")

        except ImportError:
            logger.warning("torch/transformers not installed, using fallback mode")
            self.model = None
            self.tokenizer = None
            self._model_loaded = True
            self._loading = False
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model = None
            self.tokenizer = None
            self._model_loaded = True
            self._loading = False

    def preload(self):
        if not self._model_loaded and not self._loading:
            self._load_model()

    def is_ready(self) -> bool:
        return self._model_loaded and self.model is not None and self.tokenizer is not None

    def generate_response(
        self,
        user_input: str,
        history: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> str:
        self._load_model()

        if self.model is None or self.tokenizer is None:
            return self._fallback_response(user_input)

        try:
            import torch

            if system_prompt is None:
                system_prompt = "你是Chatbot，一个智能、友好、乐于助人的AI助手。你善于理解用户的需求，提供准确、有价值的回答。回答时条理清晰、语言自然流畅。"

            messages = [{"role": "system", "content": system_prompt}]

            if history:
                recent_history = history[-MAX_HISTORY_TURNS * 2:]
                for msg in recent_history:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", ""),
                    })

            messages.append({"role": "user", "content": user_input})

            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

            input_ids = self.tokenizer.encode(text, return_tensors="pt").to(self.device)

            if input_ids.shape[1] > MAX_CONTEXT_LENGTH:
                input_ids = input_ids[:, -MAX_CONTEXT_LENGTH:]

            with torch.no_grad():
                outputs = self.model.generate(
                    input_ids,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    repetition_penalty=1.15,
                    no_repeat_ngram_size=3,
                    use_cache=True,
                )

            new_tokens = outputs[0][input_ids.shape[1]:]
            response = self.tokenizer.decode(new_tokens, skip_special_tokens=True)

            return response.strip() if response.strip() else "抱歉，我暂时无法回答这个问题，请换个方式描述一下。"

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return self._fallback_response(user_input)

    def _fallback_response(self, user_input: str) -> str:
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

        return "抱歉，我目前服务繁忙，请稍后再试。你也可以尝试换个方式描述你的问题。"

    def get_suggestions(self, user_input: str) -> list[str]:
        suggestions = []
        if len(user_input) >= 2:
            common_topics = [
                "帮我解释一下",
                "能举个例子吗",
                "还有其他方法吗",
                "详细说说",
                "总结一下",
            ]
            suggestions = common_topics[:3]
        return suggestions


_model_instance: Optional[TransformerChatModel] = None


def get_chat_model() -> TransformerChatModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = TransformerChatModel()
    return _model_instance
