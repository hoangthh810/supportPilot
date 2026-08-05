import json
import logging

from backend.apps.support_api.core.config import Settings
from backend.apps.support_api.core.logging import RedactingJsonFormatter


def test_json_formatter_redacts_known_secrets_and_bearer_tokens(settings: Settings) -> None:
    secret = settings.internal_service_token.get_secret_value()
    record = logging.LogRecord(
        name="supportpilot.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=(
            f"dsn={settings.support_database_url.get_secret_value()} "
            f"Authorization: Bearer {secret}"
        ),
        args=(),
        exc_info=None,
    )

    rendered = RedactingJsonFormatter(settings.secret_values()).format(record)
    payload = json.loads(rendered)

    assert secret not in rendered
    assert settings.support_database_url.get_secret_value() not in rendered
    assert "[REDACTED]" in payload["message"]
