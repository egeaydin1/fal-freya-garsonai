from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    FAL_KEY: str
    OPENROUTER_API_KEY: str
    
    # Voice pipeline selection: "v1" (original) or "v2" (optimized with caching)
    VOICE_PIPELINE: str = "v2"
    
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5256000  # ~10 years (practically no expiry)
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
