import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Supabase config
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # Redis config (support both connection string and separate url/token)
    REDIS_URL: str = ""
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""

    # Gemini config
    GEMINI_API_KEY: str = ""

    # Image Gen Endpoint (Kaggle ngrok URL)
    IMAGE_GEN_URL: str = ""
    
    # Mock settings
    MOCK_IMAGE_GEN: bool = True

    # Cloudflare R2 / S3 Config (Optional)
    R2_BUCKET_NAME: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_ENDPOINT_URL: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
