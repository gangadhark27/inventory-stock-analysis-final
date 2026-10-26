import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key-change-in-prod-8f92b7c6")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Instance directory for database (Vercel uses /tmp for ephemeral storage)
    if os.environ.get("VERCEL"):
        INSTANCE_DIR = Path("/tmp")
    else:
        INSTANCE_DIR = BASE_DIR / "instance"
        INSTANCE_DIR.mkdir(exist_ok=True)
    
    _raw_db_url = os.environ.get("DATABASE_URL")
    if _raw_db_url and _raw_db_url.startswith("postgres://"):
        _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = _raw_db_url or f"sqlite:///{INSTANCE_DIR / 'inventory.db'}"
    
    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_TIME_LIMIT = None  # Prevent premature token expiry in dev demo


class TestConfig(Config):
    """Configuration for automated test suite."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key"
