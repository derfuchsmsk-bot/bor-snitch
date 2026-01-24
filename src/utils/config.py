from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    TELEGRAM_TOKEN: str
    WEBHOOK_URL: str
    GCP_PROJECT_ID: str
    GCP_LOCATION: str = "us-central1"
    SECRET_TOKEN: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
