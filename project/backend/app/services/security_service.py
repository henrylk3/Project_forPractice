import re
from typing import Optional

from loguru import logger


XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript\s*:",
    r"on\w+\s*=",
    r"<iframe[^>]*>",
    r"<object[^>]*>",
    r"<embed[^>]*>",
    r"eval\s*\(",
    r"expression\s*\(",
]

SQL_INJECTION_PATTERNS = [
    r"(\bunion\b.*\bselect\b)",
    r"(\bselect\b.*\bfrom\b)",
    r"(\binsert\b.*\binto\b)",
    r"(\bdelete\b.*\bfrom\b)",
    r"(\bdrop\b.*\btable\b)",
    r"(\bupdate\b.*\bset\b)",
    r"(--\s*$)",
    r"(;\s*\w)",
    r"('\s*(or|and)\s+')",
    r"(\b1\s*=\s*1\b)",
]

PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",
    r"\.\.\\",
    r"%2e%2e",
    r"%252e",
]

SENSITIVE_INFO_PATTERNS = [
    r"\b\d{16,19}\b",
    r"\b\d{6}\s*\d{4}\s*\d{4}\s*\d{4}\b",
]

COMPILED_XSS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in XSS_PATTERNS]
COMPILED_SQL = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in SQL_INJECTION_PATTERNS]
COMPILED_PATH = [re.compile(p, re.IGNORECASE) for p in PATH_TRAVERSAL_PATTERNS]
COMPILED_SENSITIVE = [re.compile(p) for p in SENSITIVE_INFO_PATTERNS]


class SecurityService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def sanitize_input(self, text: str) -> str:
        if not text:
            return text

        sanitized = text
        sanitized = re.sub(r"<[^>]+>", "", sanitized)
        sanitized = sanitized.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        sanitized = re.sub(r"[ \t]+", " ", sanitized).strip()

        return sanitized

    def check_xss(self, text: str) -> bool:
        for pattern in COMPILED_XSS:
            if pattern.search(text):
                logger.warning(f"XSS attempt detected: {text[:100]}")
                return True
        return False

    def check_sql_injection(self, text: str) -> bool:
        for pattern in COMPILED_SQL:
            if pattern.search(text):
                if any(kw in text.lower() for kw in ["drop", "delete", "insert", "update", "exec", "execute"]):
                    logger.warning(f"SQL injection attempt detected: {text[:100]}")
                    return True
        return False

    def check_path_traversal(self, text: str) -> bool:
        for pattern in COMPILED_PATH:
            if pattern.search(text):
                logger.warning(f"Path traversal attempt detected: {text[:100]}")
                return True
        return False

    def check_sensitive_info(self, text: str) -> dict:
        found = {}
        for i, pattern in enumerate(COMPILED_SENSITIVE):
            matches = pattern.findall(text)
            if matches:
                types = ["bank_card", "id_card"]
                if i < len(types):
                    found[types[i]] = len(matches)
        return found

    def validate_message(self, text: str) -> tuple[bool, str]:
        if not text or not text.strip():
            return False, "消息内容不能为空"

        if self.check_xss(text):
            return False, "消息包含不安全内容"

        if self.check_sql_injection(text):
            return False, "消息包含不安全内容"

        if self.check_path_traversal(text):
            return False, "消息包含不安全内容"

        sensitive = self.check_sensitive_info(text)
        if sensitive:
            logger.warning(f"Sensitive info detected in message: {sensitive}")

        return True, ""

    def mask_sensitive_info(self, text: str) -> str:
        masked = text
        for pattern in COMPILED_SENSITIVE:
            masked = pattern.sub(lambda m: m.group()[:3] + "****" + m.group()[-4:], masked)
        return masked


_security_service: Optional[SecurityService] = None


def get_security_service() -> SecurityService:
    global _security_service
    if _security_service is None:
        _security_service = SecurityService()
    return _security_service
