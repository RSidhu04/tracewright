import re
from typing import Any

MASK = "[REDACTED]"
SENSITIVE = re.compile(r"password|secret|token|authorization|api.?key|cookie", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
KEY = re.compile(r"\bsk-[A-Za-z0-9_-]+")


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {scrub(str(k), secrets): MASK if SENSITIVE.search(str(k)) else redact(v, secrets)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        return scrub(value, secrets)
    return value


def scrub(value: str, secrets: tuple[str, ...]) -> str:
    for secret in sorted(filter(None, secrets), key=len, reverse=True):
        value = value.replace(secret, MASK)
    return KEY.sub(MASK, BEARER.sub(MASK, EMAIL.sub(MASK, value)))
