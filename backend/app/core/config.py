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
    database_url: str = "postgresql+asyncpg://app:pitch-analyzer-secret@localhost:5432/sales_analyzer"
    sync_database_url: str = "postgresql+psycopg2://app:pitch-analyzer-secret@localhost:5432/sales_analyzer"
    
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
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    
    # Analysis Settings
    max_video_duration_seconds: int = 1800  # 30 minutes for longer videos
    max_video_size_mb: int = 1000
    analysis_chunk_duration: int = 30  # seconds
    frame_extraction_fps: float = 0.3  # 0.3 fps = 1 frame every 3.3 seconds (reduced for speed)

    # Validation Gates
    min_video_duration_seconds: int = 25  # Reject clips shorter than this
    min_transcript_words: int = 20  # Reject transcripts with fewer words
    # Comma-separated ISO 639-1 codes, e.g. "en,es". Empty string = all languages accepted.
    supported_languages: str = ""
    # Enable LLM-based relevance classifier (requires a working LLM backend)
    relevance_check_enabled: bool = False
    
    # Webhook Settings
    webhook_url: str = ""  # URL to call when analysis completes
    webhook_timeout: int = 30  # seconds
    webhook_enabled: bool = False
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173", "*"]
    
    # RunPod
    runpod_endpoint_id: str = ""
    runpod_api_key: str = ""
    use_runpod: bool = False  # Set True to use RunPod instead of local/Celery
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v
    
    @field_validator("sync_database_url", mode="before")
    @classmethod
    def derive_sync_url(cls, v, info):
        """Auto-derive sync_database_url from database_url if not explicitly set."""
        if v and v != "postgresql+psycopg2://app:pitch-analyzer-secret@localhost:5432/sales_analyzer":
            return v
        # Try to derive from database_url
        db_url = info.data.get("database_url", "")
        if db_url.startswith("sqlite+aiosqlite"):
            return db_url.replace("sqlite+aiosqlite", "sqlite")
        if db_url.startswith("postgresql+asyncpg"):
            return db_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
        return v
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def max_video_size_bytes(self) -> int:
        return self.max_video_size_mb * 1024 * 1024

    @property
    def supported_language_list(self) -> List[str]:
        """Return list of supported ISO 639-1 language codes (empty = all accepted)."""
        if not self.supported_languages:
            return []
        return [lang.strip().lower() for lang in self.supported_languages.split(",") if lang.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
