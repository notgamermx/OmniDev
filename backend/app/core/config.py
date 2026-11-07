import os
from pathlib import Path
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SOURCE_ROOT = Path(__file__).resolve().parents[3]
ROOT_DIR = Path(
    os.environ.get(
        "OMNIDEV_HOME",
        str(
            SOURCE_ROOT
            if (SOURCE_ROOT / "pyproject.toml").exists()
            else Path.home() / ".omnidev"
        ),
    )
).resolve()


class Settings(BaseSettings):
    APP_NAME: str = "Personal AI Development Environment"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    DATABASE_URL: str = f"sqlite:///{(ROOT_DIR / 'data' / 'app.db').as_posix()}"
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    API_HOST: str = "127.0.0.1"
    API_PORT: int = Field(default=8000, ge=1, le=65535)
    SECRET_KEY: str = "development-only-key"
    TERMINAL_ENABLED: bool = False
    PROJECT_ROOT: Path = ROOT_DIR / "projects"
    API_TOKEN: SecretStr | None = None
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://tauri.localhost",
        "tauri://localhost",
    ]
    PROVIDER_URLS: dict[str, str] = {}
    PROVIDER_FALLBACKS: list[dict[str, str]] = []

    # AI Provider Configuration (use SecretStr for API keys to prevent logging)
    OPENAI_API_KEY: SecretStr | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_TIMEOUT: float = 60.0
    OPENAI_MAX_RETRIES: int = 3

    GEMINI_API_KEY: SecretStr | None = None
    GROQ_API_KEY: SecretStr | None = None
    OPENROUTER_API_KEY: SecretStr | None = None
    MISTRAL_API_KEY: SecretStr | None = None
    COHERE_API_KEY: SecretStr | None = None
    NVIDIA_API_KEY: SecretStr | None = None
    CEREBRAS_API_KEY: SecretStr | None = None
    HF_TOKEN: SecretStr | None = None
    DEEPINFRA_API_KEY: SecretStr | None = None
    TOGETHER_API_KEY: SecretStr | None = None
    SAMBANOVA_API_KEY: SecretStr | None = None
    CLOUDFLARE_API_TOKEN: SecretStr | None = None
    CLOUDFLARE_ACCOUNT_ID: str | None = None

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("PROJECT_ROOT")
    @classmethod
    def project_root_absolute(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @field_validator("PROVIDER_FALLBACKS")
    @classmethod
    def validate_fallbacks(cls, value):
        for entry in value:
            if set(entry) != {"provider", "model"} or not all(entry.values()):
                raise ValueError("Each fallback needs provider and model")
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        normalized = value.upper()
        if normalized not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("API_HOST")
    @classmethod
    def validate_api_host(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(char.isspace() for char in normalized):
            raise ValueError("API_HOST must be a non-empty hostname or IP address")
        return normalized

    @field_validator("DATABASE_URL")
    @classmethod
    def resolve_sqlite_path(cls, value: str) -> str:
        prefix = "sqlite:///"
        if not value.startswith(prefix) or value == "sqlite:///:memory:":
            return value
        raw_path, separator, query = value[len(prefix) :].partition("?")
        database_path = Path(raw_path)
        if not database_path.is_absolute():
            database_path = ROOT_DIR / database_path
        resolved = f"{prefix}{database_path.resolve().as_posix()}"
        return f"{resolved}?{query}" if separator else resolved

    @model_validator(mode="after")
    def validate_secret(self):
        if (
            self.ENVIRONMENT.lower() not in {"development", "dev", "test"}
            and self.DEBUG
        ):
            raise ValueError("DEBUG must be false outside development")
        if self.ENVIRONMENT.lower() not in {"development", "dev", "test"}:
            if self.SECRET_KEY == "development-only-key" or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "Set SECRET_KEY to a unique value of at least 32 characters outside development"
                )
        if self.API_HOST not in {"127.0.0.1", "localhost", "::1"} and not (
            self.API_TOKEN and len(self.API_TOKEN.get_secret_value()) >= 32
        ):
            raise ValueError(
                "Set API_TOKEN to at least 32 characters before binding remotely"
            )
        return self


settings = Settings()
