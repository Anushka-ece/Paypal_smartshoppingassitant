import concurrent.futures
import json
import logging
import re
from typing import List, Optional

import google.generativeai as genai
from app.config import GEMINI_API_KEY
from app.services.embedding_service import Tier1Classifier
from app.services.reputation_service import ReputationService

logger = logging.getLogger(__name__)

tier1_classifier = Tier1Classifier()
reputation_service = ReputationService()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# Configure genai if valid API key is present
if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("mock") and not GEMINI_API_KEY.startswith("test"):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.warning(f"Failed to configure Gemini API: {e}")


def _clean_merchant_string(merchant_name: str) -> str:
    """Provides a cleaned human-readable merchant name."""
    if not merchant_name:
        return "Unknown Merchant"
    cleaned = re.sub(r"[*#]\S+", "", merchant_name)
    cleaned = re.sub(r"\b(store|inc|corp|llc|co|\.com)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title() if cleaned else merchant_name.strip()


def _fallback_rule_classifier(
    merchant_name: str,
    description: str = "",
    amount: float = 0.0,
    reason: str = "Keyword rule fallback",
) -> dict:
    """
    Keyword-matching rule classifier fallback used when Gemini API
    exceeds 500ms timeout, fails, encounters rate limiting, or has no key configured.
    """
    combined = f"{merchant_name or ''} {description or ''}".lower()
    clean_name = _clean_merchant_string(merchant_name)

    # 1. Transport / Fuel
    if any(k in combined for k in ["chevron", "shell", "exxon", "bp", "gas", "fuel", "valero", "speedway", "mobil"]):
        return {
            "category": "Transport",
            "subcategory": "Fuel",
            "merchant_clean_name": clean_name,
            "confidence": 0.85,
            "tags": ["transport", "fuel", "gas"],
            "reasoning": f"{reason}: Matched fuel/gas station keywords",
        }
    if any(k in combined for k in ["uber", "lyft", "taxi", "cab", "metro", "transit", "parking", "toll"]):
        return {
            "category": "Transport",
            "subcategory": "Transit & Rideshare",
            "merchant_clean_name": clean_name,
            "confidence": 0.85,
            "tags": ["transport", "transit"],
            "reasoning": f"{reason}: Matched transit/rideshare keywords",
        }

    # 2. Food & Dining
    if any(k in combined for k in ["bakery", "cafe", "coffee", "boba", "starbucks", "dunkin", "tea"]):
        return {
            "category": "Food & Dining",
            "subcategory": "Coffee & Bakeries",
            "merchant_clean_name": clean_name,
            "confidence": 0.85,
            "tags": ["food", "dining", "coffee"],
            "reasoning": f"{reason}: Matched coffee/bakery keywords",
        }
    if any(k in combined for k in ["restaurant", "pizza", "burger", "tacos", "diner", "grill", "bistro", "chipotle", "sandwich", "bar"]):
        return {
            "category": "Food & Dining",
            "subcategory": "Restaurants",
            "merchant_clean_name": clean_name,
            "confidence": 0.85,
            "tags": ["food", "dining", "restaurants"],
            "reasoning": f"{reason}: Matched restaurant/dining keywords",
        }

    # 3. Health & Wellness / Pharmacy
    if any(k in combined for k in ["cvs", "walgreens", "pharmacy", "rite aid", "rx", "medicine", "clinic", "health"]):
        return {
            "category": "Health & Wellness",
            "subcategory": "Pharmacy & Medicine",
            "merchant_clean_name": clean_name,
            "confidence": 0.85,
            "tags": ["health", "wellness", "pharmacy"],
            "reasoning": f"{reason}: Matched pharmacy/wellness keywords",
        }

    # 4. Groceries
    if any(k in combined for k in ["grocer", "supermarket", "trader joe", "safeway", "kroger", "whole foods", "aldi", "costco", "market"]):
        return {
            "category": "Groceries",
            "subcategory": "Supermarket",
            "merchant_clean_name": clean_name,
            "confidence": 0.85,
            "tags": ["groceries", "supermarket"],
            "reasoning": f"{reason}: Matched grocery keywords",
        }

    # 5. Education
    if any(k in combined for k in ["kumon", "tutoring", "school", "tuition", "academy", "books", "course", "udemy", "coursera", "college"]):
        return {
            "category": "Education",
            "subcategory": "Learning & Tutoring",
            "merchant_clean_name": clean_name,
            "confidence": 0.85,
            "tags": ["education", "learning"],
            "reasoning": f"{reason}: Matched education keywords",
        }

    # 6. Gaming & Entertainment
    if any(k in combined for k in ["steam", "playstation", "xbox", "nintendo", "gaming", "game", "roblox"]):
        return {
            "category": "Gaming",
            "subcategory": "Digital Games",
            "merchant_clean_name": clean_name,
            "confidence": 0.85,
            "tags": ["gaming", "entertainment"],
            "reasoning": f"{reason}: Matched gaming keywords",
        }
    if any(k in combined for k in ["netflix", "spotify", "hulu", "disney", "theater", "cinema", "amc", "movie"]):
        return {
            "category": "Entertainment",
            "subcategory": "Media & Entertainment",
            "merchant_clean_name": clean_name,
            "confidence": 0.85,
            "tags": ["entertainment", "media"],
            "reasoning": f"{reason}: Matched entertainment keywords",
        }

    # 7. Home Improvement
    if any(k in combined for k in ["hardware", "home depot", "lowes", "tools", "lumber", "ace hardware"]):
        return {
            "category": "Home Improvement",
            "subcategory": "Hardware Tools",
            "merchant_clean_name": clean_name,
            "confidence": 0.85,
            "tags": ["home_improvement", "tools"],
            "reasoning": f"{reason}: Matched hardware keywords",
        }

    # 8. Shopping
    if any(k in combined for k in ["amazon", "target", "walmart", "clothing", "apparel", "shoes", "mall", "store"]):
        return {
            "category": "Shopping",
            "subcategory": "Retail",
            "merchant_clean_name": clean_name,
            "confidence": 0.75,
            "tags": ["shopping", "retail"],
            "reasoning": f"{reason}: Matched retail shopping keywords",
        }

    # Default fallback
    return {
        "category": "General",
        "subcategory": "Other",
        "merchant_clean_name": clean_name,
        "confidence": 0.50,
        "tags": ["general", "uncategorized"],
        "reasoning": f"{reason}: Default fallback categorization",
    }


def _call_gemini_llm(merchant_name: str, description: str, amount: float) -> dict:
    """Invokes Gemini Flash model with structured JSON output."""
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("mock") or GEMINI_API_KEY.startswith("test"):
        raise ValueError("Gemini API key is unset or mock")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    )

    prompt = f"""You are a financial transaction categorization AI for a family budgeting platform.
Categorize this transaction into a structured JSON object.

Merchant Name: {merchant_name}
Description: {description}
Amount: ${amount:.2f}

Return ONLY a JSON object with this exact schema:
{{
  "category": string,
  "subcategory": string,
  "merchant_clean_name": string,
  "confidence": float,
  "tags": [string],
  "reasoning": string
}}
"""
    response = model.generate_content(prompt)
    raw_text = response.text.strip()
    return json.loads(raw_text)


def classify_transaction(
    merchant_name: str,
    description: str = "",
    amount: float = 0.0,
    family_id: Optional[int] = None,
) -> dict:
    """
    Two-Tier Expense Categorization Engine:
    1. Tier 1 Fast Path (<5ms): Custom family-specific override learning cache and standard merchant regexes.
    2. Tier 2 LLM: Gemini Flash with structured output schema and 500ms circuit breaker.
    3. Safe Fallback: Keyword-matching rule classifier on timeout, API failure, rate limiting, or missing credentials.
    """
    # 1. Tier 1 check (Family override + Fast path)
    t1_result = tier1_classifier.classify(merchant_name, amount=amount, family_id=family_id)
    if t1_result:
        return t1_result

    # 2. Tier 2: Call Gemini Flash with 500ms timeout circuit breaker
    try:
        future = _executor.submit(_call_gemini_llm, merchant_name, description, amount)
        result = future.result(timeout=0.5)  # 500ms timeout
        if isinstance(result, dict) and "category" in result:
            return result
    except concurrent.futures.TimeoutError:
        logger.warning(f"Gemini classification timed out (>500ms) for merchant '{merchant_name}'")
        return _fallback_rule_classifier(
            merchant_name=merchant_name,
            description=description,
            amount=amount,
            reason="Gemini 500ms timeout circuit breaker fallback",
        )
    except Exception as exc:
        logger.warning(f"Gemini classification failed for merchant '{merchant_name}': {exc}")
        return _fallback_rule_classifier(
            merchant_name=merchant_name,
            description=description,
            amount=amount,
            reason=f"Gemini circuit breaker error fallback: {exc}",
        )

    return _fallback_rule_classifier(
        merchant_name=merchant_name,
        description=description,
        amount=amount,
        reason="Default rule fallback",
    )


def _fallback_policy_evaluator(rules: list, transaction_data: dict, reason: str = "Fallback rule evaluator") -> dict:
    """
    Keyword and heuristic rule evaluator when LLM times out or is unreachable.
    """
    amount = float(transaction_data.get("amount", 0.0))
    merchant = str(transaction_data.get("merchant_name", "")).lower()
    category = str(transaction_data.get("category", "")).lower()
    description = str(transaction_data.get("description", "")).lower()
    combined_text = f"{merchant} {category} {description}"

    matched_rules = []
    is_flagged = False
    risk_level = "LOW"

    for rule in rules:
        rule_lower = rule.lower()

        # Check amount thresholds in rule (e.g. "over $25", "exceeds $50", "> 10")
        threshold_match = re.search(r"(?:over|exceeds?|above|more than|\$|>)\s*\$?(\d+(?:\.\d{1,2})?)", rule_lower)
        if threshold_match:
            limit = float(threshold_match.group(1))
            if amount > limit:
                # Check if rule also restricts specific category (e.g. "on video games", "on gaming")
                if any(kw in rule_lower for kw in ["gaming", "game", "video game"]):
                    if any(kw in combined_text for kw in ["game", "gaming", "steam", "playstation", "xbox", "roblox", "nintendo"]):
                        matched_rules.append(rule)
                        is_flagged = True
                elif any(kw in rule_lower for kw in ["food", "dining", "treats"]):
                    if any(kw in combined_text for kw in ["food", "dining", "restaurant", "cafe", "coffee"]):
                        matched_rules.append(rule)
                        is_flagged = True
                else:
                    # General amount limit
                    matched_rules.append(rule)
                    is_flagged = True

        # Check keyword restrictions without amount (e.g. "Flag video games", "Flag adult", "Flag gambling")
        for kw in ["video game", "gaming", "crypto", "gambling", "adult", "vape"]:
            if kw in rule_lower and kw in combined_text:
                if rule not in matched_rules:
                    matched_rules.append(rule)
                is_flagged = True

    if is_flagged:
        risk_level = "HIGH" if amount > 50.0 else "MEDIUM"
        summary = f"{reason}: Purchase of ${amount:.2f} at '{transaction_data.get('merchant_name')}' matched {len(matched_rules)} rule(s)."
        requires_immediate = True
    else:
        summary = f"{reason}: Purchase of ${amount:.2f} complies with family rules."
        requires_immediate = False

    return {
        "is_flagged": is_flagged,
        "risk_level": risk_level,
        "matched_rules": matched_rules,
        "summary_for_parent": summary,
        "requires_immediate_action": requires_immediate,
    }


def _call_gemini_policy_llm(rules: list, transaction_data: dict) -> dict:
    """Invokes Gemini Flash model with structured JSON output for policy guardrails."""
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("mock") or GEMINI_API_KEY.startswith("test"):
        raise ValueError("Gemini API key is unset or mock")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    )

    prompt = f"""You are an AI financial safety guardrail for a family budgeting app.
Evaluate whether this child transaction violates any of the parent-defined rules.

Parent Rules:
{chr(10).join(f"- {r}" for r in rules)}

Transaction Details:
- Merchant: {transaction_data.get('merchant_name')}
- Amount: ${transaction_data.get('amount', 0.0):.2f}
- Category: {transaction_data.get('category')}
- Subcategory: {transaction_data.get('subcategory')}
- Description: {transaction_data.get('description')}

Return ONLY a JSON object with this exact schema:
{{
  "is_flagged": boolean,
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "matched_rules": [string],
  "summary_for_parent": string,
  "requires_immediate_action": boolean
}}
"""
    response = model.generate_content(prompt)
    raw_text = response.text.strip()
    return json.loads(raw_text)


def evaluate_policy(rules: list, transaction_data: dict) -> dict:
    """
    Two-Step Threat & Natural Language Policy Evaluation Engine:
    Step 1: Check merchant against threat blacklist (Gambling, Crypto, Unverified Keys, Adult).
    Step 2: Evaluate transaction against parent-defined natural language rules using Gemini Flash with 500ms circuit breaker.
    """
    merchant_name = transaction_data.get("merchant_name", "")

    # Step 1: Blacklist & Reputation Threat Check
    threat = reputation_service.check_merchant(merchant_name)
    if threat["is_high_risk"]:
        return {
            "is_flagged": True,
            "risk_level": "HIGH",
            "matched_rules": [f"Threat Blacklist: {threat['matched_category']}"],
            "summary_for_parent": f"High risk entity blocked: {threat['reason']}",
            "requires_immediate_action": True,
        }

    # If no custom rules defined, transaction passes
    if not rules:
        return {
            "is_flagged": False,
            "risk_level": "LOW",
            "matched_rules": [],
            "summary_for_parent": "No active family guardrails triggered.",
            "requires_immediate_action": False,
        }

    # Step 2: Evaluate with Gemini Flash or Fallback
    try:
        future = _executor.submit(_call_gemini_policy_llm, rules, transaction_data)
        result = future.result(timeout=0.5)  # 500ms timeout
        if isinstance(result, dict) and "is_flagged" in result:
            return result
    except concurrent.futures.TimeoutError:
        logger.warning(f"Gemini policy evaluation timed out (>500ms) for merchant '{merchant_name}'")
        return _fallback_policy_evaluator(
            rules=rules,
            transaction_data=transaction_data,
            reason="Gemini 500ms timeout circuit breaker fallback",
        )
    except Exception as exc:
        logger.warning(f"Gemini policy evaluation failed: {exc}")
        return _fallback_policy_evaluator(
            rules=rules,
            transaction_data=transaction_data,
            reason="Rule heuristic fallback",
        )

    return _fallback_policy_evaluator(
        rules=rules,
        transaction_data=transaction_data,
        reason="Default heuristic evaluation",
    )
