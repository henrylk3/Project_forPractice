import re
from typing import Optional

from loguru import logger


ENTITY_PATTERNS = {
    "date": {
        "patterns": [
            r"\d{4}年\d{1,2}月\d{1,2}日",
            r"\d{4}-\d{1,2}-\d{1,2}",
            r"\d{1,2}月\d{1,2}日",
            r"今天|明天|后天|昨天|前天",
            r"本周|下周|上周|这周",
        ],
        "description": "日期",
    },
    "time": {
        "patterns": [
            r"\d{1,2}点\d{0,2}分?",
            r"\d{1,2}:\d{2}",
            r"早上|上午|中午|下午|晚上|凌晨",
        ],
        "description": "时间",
    },
    "phone": {
        "patterns": [
            r"1[3-9]\d{9}",
        ],
        "description": "手机号",
    },
    "email": {
        "patterns": [
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        ],
        "description": "邮箱",
    },
    "url": {
        "patterns": [
            r"https?://[^\s]+",
            r"www\.[^\s]+",
        ],
        "description": "网址",
    },
    "number": {
        "patterns": [
            r"\d+\.?\d*",
        ],
        "description": "数字",
    },
    "location": {
        "patterns": [
            r"[北京上海广州深圳杭州成都武汉南京重庆西安]",
            r"[^\s]{2,}(省|市|区|县|镇|路|街|号)",
        ],
        "description": "地点",
    },
    "person": {
        "patterns": [
            r"(?:叫|名为|名字是|我是)\s*([^\s，。！？]{2,4})",
        ],
        "description": "人名",
    },
}


class EntityExtractor:
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
        for entity_type, config in ENTITY_PATTERNS.items():
            combined = "|".join(f"({p})" for p in config["patterns"])
            self._compiled_patterns[entity_type] = re.compile(combined, re.IGNORECASE)
        logger.info("EntityExtractor initialized")

    def extract(self, text: str) -> list[dict]:
        if not text or not text.strip():
            return []

        entities = []
        seen_spans = set()

        for entity_type, pattern in self._compiled_patterns.items():
            for match in pattern.finditer(text):
                start, end = match.start(), match.end()
                span_key = (start, end)
                if span_key in seen_spans:
                    continue
                seen_spans.add(span_key)

                entities.append({
                    "type": entity_type,
                    "value": match.group(),
                    "start": start,
                    "end": end,
                    "confidence": 0.85,
                })

        entities.sort(key=lambda x: x["start"])
        return entities


_entity_extractor: Optional[EntityExtractor] = None


def get_entity_extractor() -> EntityExtractor:
    global _entity_extractor
    if _entity_extractor is None:
        _entity_extractor = EntityExtractor()
    return _entity_extractor
