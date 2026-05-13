import re
from typing import Optional

from loguru import logger


INTENT_DEFINITIONS = {
    "greeting": {
        "patterns": [r"你好|hello|hi|嗨|早上好|下午好|晚上好|hey"],
        "description": "用户打招呼",
    },
    "farewell": {
        "patterns": [r"再见|拜拜|bye|晚安|下次见"],
        "description": "用户告别",
    },
    "question": {
        "patterns": [r"什么是|怎么|如何|为什么|哪里|哪个|多少|是否|能不能|可以.*吗|吗[？?]$"],
        "description": "用户提问",
    },
    "request": {
        "patterns": [r"帮我|请|麻烦|帮我.*一下|能不能帮我|请帮我"],
        "description": "用户请求帮助",
    },
    "complaint": {
        "patterns": [r"不好|不行|差|烂|失望|不满|投诉|退款"],
        "description": "用户投诉",
    },
    "thanks": {
        "patterns": [r"谢谢|感谢|多谢|thank|thanks|辛苦了"],
        "description": "用户感谢",
    },
    "chitchat": {
        "patterns": [r"无聊|聊聊|说说|讲讲|有趣"],
        "description": "闲聊",
    },
    "search": {
        "patterns": [r"搜索|查找|找一下|有没有|查询"],
        "description": "搜索信息",
    },
    "settings": {
        "patterns": [r"设置|配置|修改|更改|调整|切换"],
        "description": "修改设置",
    },
}


class IntentRecognizer:
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
        self._compiled_patterns = {}
        for intent, config in INTENT_DEFINITIONS.items():
            combined = "|".join(config["patterns"])
            self._compiled_patterns[intent] = re.compile(combined, re.IGNORECASE)
        logger.info("IntentRecognizer initialized with rule-based patterns")

    def recognize(self, text: str) -> dict:
        if not text or not text.strip():
            return {"intent": "unknown", "confidence": 0.0}

        scores = {}
        for intent, pattern in self._compiled_patterns.items():
            match = pattern.search(text)
            if match:
                match_length = match.end() - match.start()
                scores[intent] = min(match_length / len(text) + 0.5, 1.0)

        if not scores:
            return {"intent": "general", "confidence": 0.3}

        best_intent = max(scores, key=scores.get)
        confidence = scores[best_intent]

        return {
            "intent": best_intent,
            "confidence": round(confidence, 3),
            "all_scores": {k: round(v, 3) for k, v in sorted(scores.items(), key=lambda x: -x[1])},
        }


_intent_recognizer: Optional[IntentRecognizer] = None


def get_intent_recognizer() -> IntentRecognizer:
    global _intent_recognizer
    if _intent_recognizer is None:
        _intent_recognizer = IntentRecognizer()
    return _intent_recognizer
