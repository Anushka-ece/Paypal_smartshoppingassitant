import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/paypal_family_budget")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_BASE_URL = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
