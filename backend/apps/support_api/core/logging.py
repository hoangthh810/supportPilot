from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from backend.apps.support_api.core.config import Settings

_AUTHORIZATION_PATTERN = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*")


class RedactingJsonFormatter(logging.Formatter):
    def __init__(self, secrets: tuple[str, ...]) -> None:
        super().__init__()
        self._secrets = tuple(secret for secret in secrets if secret)

    def _redact(self, value: str) -> str:
        redacted = _AUTHORIZATION_PATTERN.sub("Bearer [REDACTED]", value)
        for secret in self._secrets:
            redacted = redacted.replace(secret, "[REDACTED]")
        return redacted

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self._redact(record.getMessage()),
        }
        correlation_id = getattr(record, "correlation_id", None)
        if isinstance(correlation_id, str):
            payload["correlation_id"] = correlation_id
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingJsonFormatter(settings.secret_values()))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level)

