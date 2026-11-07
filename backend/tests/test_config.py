from pathlib import Path

from app.core.config import Settings


def test_configuration_defaults_and_overrides():
    settings = Settings(
        _env_file=None,
        APP_NAME="Test App",
        API_PORT=8123,
        LOG_LEVEL="warning",
    )
    assert settings.APP_NAME == "Test App"
    assert settings.API_PORT == 8123
    assert settings.LOG_LEVEL == "WARNING"
    assert settings.TERMINAL_ENABLED is False
    db_path = Path(settings.DATABASE_URL.removeprefix("sqlite:///"))
    assert db_path.is_absolute()
