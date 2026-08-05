from fastapi import Request

from backend.apps.support_api.core.config import Settings


def get_settings(request: Request) -> Settings:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("application settings are unavailable")
    return settings

