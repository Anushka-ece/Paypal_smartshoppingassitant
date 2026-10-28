import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_paypal_family.db")
os.environ.setdefault("APP_JWT_SECRET", "test-jwt-secret-for-unit-tests-only-32bytes")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "")
os.environ.setdefault("PAYPAL_CLIENT_ID", "")
os.environ.setdefault("PAYPAL_CLIENT_SECRET", "")
os.environ.setdefault("PAYPAL_WEBHOOK_ID", "")
os.environ.setdefault("GEMINI_API_KEY", "")
