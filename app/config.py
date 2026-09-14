from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str | None = None
    SUPABASE_DB_URL: str | None = None
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Local Dev Fields (Made optional to avoid production missing errors)
    DB_HOST: str | None = None
    DB_NAME: str | None = None
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    DB_PORT: str | None = None

    REDIS_HOST: str | None = None
    REDIS_PORT: str | None = None

    RABBITMQ_HOST: str | None = None
    RABBITMQ_PORT: str | None = None
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()