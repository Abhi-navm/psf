"""
Core configuration module for Sales Pitch Analyzer.
Loads settings from environment variables with validation.
"""

from functools import lru_cache
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Environment
    environment: str = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./data/sales_analyzer.db"
    
    # Redis & Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_use_redis: bool = True  # Docker Redis is available
    
    # Storage
    storage_backend: str = "local"  # local or r2
    local_storage_path: str = "./data/uploads"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "sales-pitch-videos"
    
    # AI Models
    whisper_model: str = "large-v3"  # tiny, base, small, medium, large-v3
    whisper_device: str = "cuda"  # cpu or cuda
    embedding_device: str = "cuda"  # Device for sentence transformers
    deepface_device: str = "cuda"  # Device for DeepFace (cuda or cpu)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    
    # Analysis Settings
    max_video_duration_seconds: int = 1800  # 30 minutes for longer videos
    max_video_size_mb: int = 1000
    analysis_chunk_duration: int = 30  # seconds
    frame_extraction_fps: float = 0.3  # 0.3 fps = 1 frame every 3.3 seconds (reduced for speed)
    
    # Webhook Settings
    webhook_url: str = ""  # URL to call when analysis completes
    webhook_timeout: int = 30  # seconds
    webhook_enabled: bool = False
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173", "*"]
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def max_video_size_bytes(self) -> int:
        return self.max_video_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
