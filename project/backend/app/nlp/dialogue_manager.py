import asyncio
import json
from typing import Optional

from loguru import logger

from app.nlp.transformer_model import get_chat_model
from app.nlp.intent_recognition import get_intent_recognizer
from app.nlp.entity_extraction import get_entity_extractor


FAQ_RESPONSES = {
    "greeting": "你好！我是Chatbot，很高兴见到你！有什么我可以帮助你的吗？无论是问题解答、知识科普还是日常聊天，我都在这里。",
    "farewell": "再见！期待下次与你交流，祝你一切顺利！",
    "thanks": "不客气！能帮到你是我的荣幸。如果还有其他问题，随时可以找我。",
    "question": None,
    "request": None,
    "chitchat": None,
}

INTENT_FALLBACK_MAP = {
    "question": "这是一个很好的问题。让我来为你解答：",
    "request": "好的，我来帮你处理：",
    "complaint": "非常抱歉给你带来不好的体验，我会尽力帮助你解决问题。",
    "search": "我来帮你查找相关信息：",
}


class DialogueManager:
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
        self.chat_model = get_chat_model()
        self.intent_recognizer = get_intent_recognizer()
        self.entity_extractor = get_entity_extractor()
        logger.info("DialogueManager initialized")

    async def process_message(
        self,
        user_input: str,
        history: Optional[list[dict]] = None,
        bot_role: str = "assistant",
        dialogue_style: str = "friendly",
    ) -> dict:
        intent_result = self.intent_recognizer.recognize(user_input)
        entities = self.entity_extractor.extract(user_input)

        intent = intent_result["intent"]
        confidence = intent_result["confidence"]

        logger.info(f"Intent: {intent} (confidence: {confidence}), Entities: {len(entities)}")

        if intent in FAQ_RESPONSES and FAQ_RESPONSES[intent] is not None and confidence > 0.7:
            response_content = FAQ_RESPONSES[intent]
        else:
            system_prompt = self._build_system_prompt(intent, confidence)
            loop = asyncio.get_event_loop()
            response_content = await loop.run_in_executor(
                None,
                self.chat_model.generate_response,
                user_input,
                history,
                system_prompt,
            )

        suggestions = self.chat_model.get_suggestions(user_input)

        return {
            "content": response_content,
            "intent": intent,
            "intent_confidence": confidence,
            "entities": entities,
            "suggestions": suggestions,
        }

    def _build_system_prompt(self, intent: str, confidence: float) -> str:
        base_prompt = "你是Chatbot，一个智能、友好、乐于助人的AI助手。你善于理解用户的需求，提供准确、有价值的回答。回答时条理清晰、语言自然流畅。"

        intent_hint = INTENT_FALLBACK_MAP.get(intent)
        if intent_hint and confidence > 0.5:
            base_prompt += f"\n当前用户意图可能是{intent}，请针对性地回应。"

        return base_prompt

    def get_typing_suggestions(self, partial_input: str) -> list[str]:
        if not partial_input or len(partial_input) < 1:
            return ["你好", "帮我", "什么是"]

        quick_suggestions = {
            "你": ["你好", "你是谁", "你能做什么"],
            "帮": ["帮我", "帮我解释", "帮我搜索"],
            "什": ["什么是", "什么时候", "什么意思"],
            "怎": ["怎么样", "怎么做", "怎么回事"],
            "为": ["为什么", "为什么这样"],
            "如": ["如何", "如何做", "如果"],
        }

        first_char = partial_input[0]
        if first_char in quick_suggestions:
            return quick_suggestions[first_char]

        return []


_dialogue_manager: Optional[DialogueManager] = None


def get_dialogue_manager() -> DialogueManager:
    global _dialogue_manager
    if _dialogue_manager is None:
        _dialogue_manager = DialogueManager()
    return _dialogue_manager
