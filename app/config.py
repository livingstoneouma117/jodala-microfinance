from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    secret_key: str = "dev-secret-change-me"
    database_url: str = "sqlite:///./microlend.db"
    access_token_expire_minutes: int = 120
    admin_username: str = "admin"
    admin_password: str = "admin123"
    openai_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
