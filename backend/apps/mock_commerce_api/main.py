from backend.apps.mock_commerce_api.app import create_mock_commerce_app
from backend.apps.mock_commerce_api.core.config import load_mock_commerce_settings
from backend.apps.mock_commerce_api.core.logging import configure_logging

settings = load_mock_commerce_settings()
configure_logging(settings.secret_values())
app = create_mock_commerce_app(settings)
