import google.generativeai as genai
from app.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

def classify_transaction(merchant_name: str, description: str, amount: float):
    # Tier 2 Gemini Flash classifier implementation placeholder
    pass

def evaluate_policy(rules: list, transaction_data: dict):
    # LLM policy evaluator implementation placeholder
    pass
