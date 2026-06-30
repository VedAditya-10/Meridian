"""
Purpose: Core application configuration management.
Responsibilities: 
- Load and validate environment variables using Pydantic V2.
- Construct Database and Redis connection strings.
- Configure production-grade structured logging.
Dependencies: pydantic, pydantic-settings, logging, sys.
"""

import logging
import sys
import uuid
from typing import Any, List, Union

from pydantic import AnyHttpUrl, RedisDsn, field_validator
from pydantic_core.core_schema import ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings validated via Pydantic.
    Fails fast on startup if required environment variables are missing.
    """
    PROJECT_NAME: str = "Meridian"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "production"

    # Fixed UUID for the single-store Meridian deployment.
    MERIDIAN_STORE_ID: uuid.UUID = uuid.UUID("a1b2c3d4-0001-4000-8000-000000000001")
    MAX_CAMERAS: int = 6
    
    # Security / CORS
    # Principal Note: We use List[str] instead of List[AnyHttpUrl] because Pydantic V2's
    # AnyHttpUrl serializes to a Url object that breaks string comparison in CORSMiddleware.
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parses a comma-separated string of origins into a list."""
        if isinstance(v, str):
            if v.startswith("["):
                import json
                return json.loads(v)
            return [i.strip() for i in v.split(",")]
        return v

    # PostgreSQL config
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "store_intelligence"
    POSTGRES_PORT: int = 5432
    SQLALCHEMY_DATABASE_URI: str | None = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None, info: ValidationInfo) -> Any:
        """Constructs the asyncpg database URI from individual components."""
        if isinstance(v, str):
            # Render/Neon often provides postgresql:// URIs with unsupported kwargs 
            # like sslmode=require or channel_binding=disable. asyncpg strictly expects ssl=require.
            import urllib.parse
            
            uri = v
            if uri.startswith("postgresql://"):
                uri = uri.replace("postgresql://", "postgresql+asyncpg://", 1)
                
            # Parse the URL and clean up query parameters
            parsed = urllib.parse.urlparse(uri)
            query_params = urllib.parse.parse_qs(parsed.query)
            
            # Keep only 'ssl' or convert 'sslmode' to 'ssl'. Drop everything else (like channel_binding).
            new_query = {}
            if 'sslmode' in query_params or 'ssl' in query_params:
                new_query['ssl'] = 'require'
                
            new_query_string = urllib.parse.urlencode(new_query)
            
            # Reconstruct the URL
            clean_uri = urllib.parse.urlunparse((
                parsed.scheme, parsed.netloc, parsed.path, 
                parsed.params, new_query_string, parsed.fragment
            ))
            
            return clean_uri
        
        values = info.data
        user = values.get("POSTGRES_USER")
        password = values.get("POSTGRES_PASSWORD")
        host = values.get("POSTGRES_SERVER")
        port = values.get("POSTGRES_PORT")
        db = values.get("POSTGRES_DB")
        
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    # Redis config
    REDIS_URI: RedisDsn | str = "redis://localhost:6379/0"

    # Logging config
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")


def setup_logging(level: str) -> logging.Logger:
    """
    Configures structured JSON logging for production observability.
    Returns a configured root logger.
    """
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Use standard StreamHandler for containerized environments (Docker logs)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # For production, log in JSON format for easy ingestion by ELK/Datadog
    log_format = (
        '{"time": "%(asctime)s", "level": "%(levelname)s", '
        '"logger": "%(name)s", "message": "%(message)s"}'
    )
    
    formatter = logging.Formatter(log_format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

try:
    settings = Settings()
except Exception as e:
    # Failsafe logging before structured logging is set up
    print(f"CRITICAL: Failed to load configuration. {e}", file=sys.stderr)
    sys.exit(1)

# Initialize logging immediately on import
logger = setup_logging(settings.LOG_LEVEL)
logger.info("Configuration and structured logging initialized successfully.")
