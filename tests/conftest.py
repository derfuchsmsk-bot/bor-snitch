import os
import pytest
from unittest.mock import MagicMock

# Mock google auth if no credentials exist in environment
try:
    import google.auth
    from google.auth.credentials import AnonymousCredentials
    try:
        google.auth.default()
    except Exception:
        google.auth.default = lambda *args, **kwargs: (AnonymousCredentials(), "test-project")
except Exception:
    pass

# Ensure test settings are populated before importing src modules
os.environ.setdefault("TELEGRAM_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
os.environ.setdefault("WEBHOOK_URL", "https://example.com/webhook")
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_LOCATION", "us-central1")
os.environ.setdefault("SECRET_TOKEN", "test-secret-token")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-super-secure-32bytes-minimum-string-1234567890")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("ELEVENLABS_API_KEY", "test-elevenlabs-key")
os.environ.setdefault("TELEGRAM_API_ID", "123456")
os.environ.setdefault("TELEGRAM_API_HASH", "test-telegram-api-hash")
