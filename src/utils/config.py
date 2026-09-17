from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    TELEGRAM_TOKEN: str
    WEBHOOK_URL: str
    GCP_PROJECT_ID: str
    GCP_LOCATION: str = "us-central1"
    SECRET_TOKEN: str
    JWT_SECRET: str = "change-me-in-production"
    LORE_BUCKET_NAME: str | None = None
    MAIN_CHAT_ID: int = -1003893798466
    ADMIN_PASSWORD: str = ""
    ELEVENLABS_API_KEY: str = ""
    TELEGRAM_API_ID: int | None = None
    TELEGRAM_API_HASH: str | None = None
    TELEGRAM_STRING_SESSION: str = ""

    @property
    def effective_admin_password(self) -> str:
        return self.ADMIN_PASSWORD if self.ADMIN_PASSWORD else self.SECRET_TOKEN

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
