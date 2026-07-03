from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = "your_telegram_bot_token_here"
    DISCORD_BOT_TOKEN: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    MODEL: str = "qwen2.5:7b"
    DATABASE_URL: str = "sqlite:///data/hermes.db"
    LOG_LEVEL: str = "INFO"
    GEMINI_API_KEY: str | None = None

    # Derived setting: SQLite relative file path extraction
    @property
    def sqlite_db_path(self) -> str:
        if self.DATABASE_URL.startswith("sqlite:///"):
            path = self.DATABASE_URL.replace("sqlite:///", "")
            return path
        return ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
