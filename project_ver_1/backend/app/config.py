import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./paypal_family_budget.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_BASE_URL = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")
PAYPAL_REDIRECT_URI = os.getenv("PAYPAL_REDIRECT_URI", "http://localhost:3000/api/auth/callback")
PAYPAL_AUTHORIZE_URL = os.getenv("PAYPAL_AUTHORIZE_URL", "https://www.sandbox.paypal.com/signin/authorize")
PAYPAL_PAYOUTS_ENABLED = os.getenv("PAYPAL_PAYOUTS_ENABLED", "false").lower() == "true"
TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "")
APP_ENV = os.getenv("APP_ENV", "development")
APP_JWT_SECRET = os.getenv("APP_JWT_SECRET", "")
APP_JWT_ISSUER = os.getenv("APP_JWT_ISSUER", "pennypilot")
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()]
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()]


def validate_production_config() -> None:
	if APP_ENV != "production":
		return
	if len(APP_JWT_SECRET.encode("utf-8")) < 32 or APP_JWT_SECRET.startswith("replace-with-"):
		raise RuntimeError("APP_JWT_SECRET must be a non-placeholder value of at least 32 bytes in production.")
	if not TOKEN_ENCRYPTION_KEY or TOKEN_ENCRYPTION_KEY.startswith("generate-"):
		raise RuntimeError("TOKEN_ENCRYPTION_KEY must be configured in production.")
	if not PAYPAL_WEBHOOK_ID:
		raise RuntimeError("PAYPAL_WEBHOOK_ID must be configured in production.")
	if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
		raise RuntimeError("PayPal app credentials are required in production.")
	if GEMINI_API_KEY and GEMINI_API_KEY.startswith("your_"):
		raise RuntimeError("GEMINI_API_KEY must not be a placeholder in production.")
