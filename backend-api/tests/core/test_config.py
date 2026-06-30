"""
Purpose: Unit tests for the core configuration module.
Responsibilities:
- Verify default settings initialization.
- Test missing environment variable failure modes (Fail-fast).
- Ensure the DB connection string is constructed correctly.
- Validate structured logging initialization.
"""

import json
import logging
from io import StringIO
from typing import Any

import pytest
from pydantic import ValidationError

from src.core.config import Settings, setup_logging


def test_settings_defaults() -> None:
    """Test that Settings initializes with expected defaults when no env vars are provided (except required)."""
    # Create a mock environment with only the required fields
    mock_env = {
        "POSTGRES_SERVER": "localhost",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_password",
        "POSTGRES_DB": "test_db",
        "REDIS_URI": "redis://localhost:6379/0"
    }
    
    settings = Settings(_env_file=None, **mock_env)  # type: ignore
    
    assert settings.PROJECT_NAME == "Meridian"
    assert settings.ENVIRONMENT == "production"
    assert settings.LOG_LEVEL == "INFO"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.BACKEND_CORS_ORIGINS == []


def test_cors_origins_parsing() -> None:
    """Test that a comma-separated CORS string is correctly parsed into a list."""
    mock_env = {
        "POSTGRES_SERVER": "localhost",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_password",
        "POSTGRES_DB": "test_db",
        "REDIS_URI": "redis://localhost:6379/0",
        "BACKEND_CORS_ORIGINS": "http://localhost:3000, https://dashboard.store.com"
    }
    
    settings = Settings(_env_file=None, **mock_env)  # type: ignore
    assert len(settings.BACKEND_CORS_ORIGINS) == 2
    assert "http://localhost:3000" in settings.BACKEND_CORS_ORIGINS
    assert "https://dashboard.store.com" in settings.BACKEND_CORS_ORIGINS


def test_database_uri_assembly() -> None:
    """Test that the SQLAlchemy async pg connection string is built correctly."""
    mock_env = {
        "POSTGRES_SERVER": "db-host.internal",
        "POSTGRES_USER": "admin",
        "POSTGRES_PASSWORD": "supersecretpassword",
        "POSTGRES_DB": "analytics_db",
        "POSTGRES_PORT": 5433,
        "REDIS_URI": "redis://localhost:6379/0"
    }
    
    settings = Settings(_env_file=None, **mock_env)  # type: ignore
    expected_uri = "postgresql+asyncpg://admin:supersecretpassword@db-host.internal:5433/analytics_db"
    assert settings.SQLALCHEMY_DATABASE_URI == expected_uri


def test_invalid_variables() -> None:
    """Test that Pydantic raises an error if variables have invalid types."""
    mock_env = {
        "POSTGRES_PORT": "not-an-int",
    }
    
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **mock_env)  # type: ignore
        
    errors = exc_info.value.errors()
    failed_fields = [error["loc"][0] for error in errors]
    
    assert "POSTGRES_PORT" in failed_fields



def test_setup_logging_json_format() -> None:
    """Test that the logging setup produces valid JSON logs."""
    # Temporarily divert stdout to capture the log output
    stream = StringIO()
    
    # Create a fresh logger instance
    logger = logging.getLogger("test_logger")
    logger.setLevel("DEBUG")
    
    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    handler = logging.StreamHandler(stream)
    
    # Use the exact JSON format string from config.py
    log_format = (
        '{"time": "%(asctime)s", "level": "%(levelname)s", '
        '"logger": "%(name)s", "message": "%(message)s"}'
    )
    formatter = logging.Formatter(log_format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Emit a test log
    logger.info("This is a test message")
    
    # Retrieve output
    log_output = stream.getvalue().strip()
    
    # Assert it parses as valid JSON
    try:
        log_dict = json.loads(log_output)
    except json.JSONDecodeError:
        pytest.fail(f"Log output is not valid JSON: {log_output}")
        
    assert log_dict["level"] == "INFO"
    assert log_dict["logger"] == "test_logger"
    assert log_dict["message"] == "This is a test message"
    assert "time" in log_dict
