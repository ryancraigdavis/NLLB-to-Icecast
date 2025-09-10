"""
Production configuration settings for NLLB Translation API.
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # API Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    
    # CORS Configuration
    cors_origins: List[str] = ["*"]
    cors_credentials: bool = True
    cors_methods: List[str] = ["*"]
    cors_headers: List[str] = ["*"]
    
    # Logging Configuration
    log_level: str = "INFO"
    
    # Audio Configuration
    default_sample_rate: int = 16000
    default_whisper_model: str = "large-v3"
    
    # Performance Configuration
    max_connections: int = 100
    connection_timeout: int = 30
    
    # Security Configuration
    api_key: Optional[str] = None
    
    # Model Configuration
    model_cache_dir: str = "/app/models"
    torch_device: str = "auto"  # auto, cpu, cuda
    
    # Environment
    environment: str = "production"
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_prefix = "NLLB_"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings


def is_production() -> bool:
    """Check if running in production environment."""
    return settings.environment.lower() == "production"


def is_development() -> bool:
    """Check if running in development environment."""
    return settings.environment.lower() == "development"