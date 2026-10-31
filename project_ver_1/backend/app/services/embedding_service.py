import json
import logging
import re
from typing import Dict, List, Optional, Tuple

from app.api.webhooks import get_redis_client

logger = logging.getLogger(__name__)


# Standard regexes and merchant signatures for Tier-1 Fast Path (<5ms)
TIER1_RULES: List[Tuple[re.Pattern, dict]] = [
    # Rideshare & Transport
    (
        re.compile(r"\b(uber(?:\s*\*trip|\s*eats|\.com)?|uber)\b", re.IGNORECASE),
        {
            "category": "Transport",
            "subcategory": "Rideshare",
            "merchant_clean_name": "Uber",
            "confidence": 0.98,
            "tags": ["transport", "rideshare"],
            "reasoning": "Tier 1 rule: Uber rideshare/transport match",
        },
    ),
    (
        re.compile(r"\b(lyft(?:\s*\*ride)?|lyft)\b", re.IGNORECASE),
        {
            "category": "Transport",
            "subcategory": "Rideshare",
            "merchant_clean_name": "Lyft",
            "confidence": 0.98,
            "tags": ["transport", "rideshare"],
            "reasoning": "Tier 1 rule: Lyft rideshare match",
        },
    ),
    # Entertainment & Streaming
    (
        re.compile(r"\b(netflix(?:\.com)?)\b", re.IGNORECASE),
        {
            "category": "Entertainment",
            "subcategory": "Streaming",
            "merchant_clean_name": "Netflix",
            "confidence": 0.99,
            "tags": ["entertainment", "streaming", "subscription"],
            "reasoning": "Tier 1 rule: Netflix subscription match",
        },
    ),
    (
        re.compile(r"\b(spotify(?:\s*usa)?)\b", re.IGNORECASE),
        {
            "category": "Entertainment",
            "subcategory": "Music Streaming",
            "merchant_clean_name": "Spotify",
            "confidence": 0.98,
            "tags": ["entertainment", "music", "subscription"],
            "reasoning": "Tier 1 rule: Spotify music subscription match",
        },
    ),
    # Gaming
    (
        re.compile(r"\b(steam(?:\s*games|\s*powered)?|steampowered)\b", re.IGNORECASE),
        {
            "category": "Gaming",
            "subcategory": "Digital Games",
            "merchant_clean_name": "Steam",
            "confidence": 0.98,
            "tags": ["gaming", "entertainment", "software"],
            "reasoning": "Tier 1 rule: Steam gaming platform match",
        },
    ),
    (
        re.compile(r"\b(playstation|playstation\s*network|sony\s*interactive)\b", re.IGNORECASE),
        {
            "category": "Gaming",
            "subcategory": "Console Games",
            "merchant_clean_name": "PlayStation",
            "confidence": 0.98,
            "tags": ["gaming", "console", "entertainment"],
            "reasoning": "Tier 1 rule: PlayStation network match",
        },
    ),
    (
        re.compile(r"\b(xbox(?:\s*live)?|microsoft\s*xbox)\b", re.IGNORECASE),
        {
            "category": "Gaming",
            "subcategory": "Console Games",
            "merchant_clean_name": "Xbox",
            "confidence": 0.98,
            "tags": ["gaming", "console", "entertainment"],
            "reasoning": "Tier 1 rule: Xbox live/games match",
        },
    ),
    (
        re.compile(r"\b(nintendo(?:\s*eshop)?)\b", re.IGNORECASE),
        {
            "category": "Gaming",
            "subcategory": "Console Games",
            "merchant_clean_name": "Nintendo",
            "confidence": 0.98,
            "tags": ["gaming", "console", "entertainment"],
            "reasoning": "Tier 1 rule: Nintendo eShop match",
        },
    ),
    # Shopping & Retail
    (
        re.compile(r"\b(amzn|amazon(?:\.com|\s*mktp|\s*prime)?)\b", re.IGNORECASE),
        {
            "category": "Shopping",
            "subcategory": "Online Retail",
            "merchant_clean_name": "Amazon",
            "confidence": 0.98,
            "tags": ["shopping", "retail", "online"],
            "reasoning": "Tier 1 rule: Amazon online retail match",
        },
    ),
    (
        re.compile(r"\b(target(?:\s*store)?)\b", re.IGNORECASE),
        {
            "category": "Shopping",
            "subcategory": "Department Store",
            "merchant_clean_name": "Target",
            "confidence": 0.97,
            "tags": ["shopping", "retail"],
            "reasoning": "Tier 1 rule: Target department store match",
        },
    ),
    (
        re.compile(r"\b(walmart(?:\.com|\s*store)?|wal-mart)\b", re.IGNORECASE),
        {
            "category": "Shopping",
            "subcategory": "Supermarket & Retail",
            "merchant_clean_name": "Walmart",
            "confidence": 0.97,
            "tags": ["shopping", "retail", "groceries"],
            "reasoning": "Tier 1 rule: Walmart retail match",
        },
    ),
    # Food & Dining
    (
        re.compile(r"\b(starbucks(?:\s*store|\s*coffee)?|sbux)\b", re.IGNORECASE),
        {
            "category": "Food & Dining",
            "subcategory": "Coffee & Cafes",
            "merchant_clean_name": "Starbucks",
            "confidence": 0.98,
            "tags": ["food", "dining", "coffee"],
            "reasoning": "Tier 1 rule: Starbucks cafe match",
        },
    ),
    (
        re.compile(r"\b(mcdonald(?:'s|\s*restaurant)?)\b", re.IGNORECASE),
        {
            "category": "Food & Dining",
            "subcategory": "Fast Food",
            "merchant_clean_name": "McDonald's",
            "confidence": 0.98,
            "tags": ["food", "dining", "fast food"],
            "reasoning": "Tier 1 rule: McDonald's fast food match",
        },
    ),
    (
        re.compile(r"\b(doordash|door\s*dash)\b", re.IGNORECASE),
        {
            "category": "Food & Dining",
            "subcategory": "Food Delivery",
            "merchant_clean_name": "DoorDash",
            "confidence": 0.98,
            "tags": ["food", "dining", "delivery"],
            "reasoning": "Tier 1 rule: DoorDash food delivery match",
        },
    ),
    (
        re.compile(r"\b(grubhub|grub\s*hub)\b", re.IGNORECASE),
        {
            "category": "Food & Dining",
            "subcategory": "Food Delivery",
            "merchant_clean_name": "Grubhub",
            "confidence": 0.98,
            "tags": ["food", "dining", "delivery"],
            "reasoning": "Tier 1 rule: Grubhub delivery match",
        },
    ),
    # Tech & Subscriptions
    (
        re.compile(r"\b(apple(?:\.com/bill|\s*store|\s*services)?)\b", re.IGNORECASE),
        {
            "category": "Electronics & Services",
            "subcategory": "Digital Services",
            "merchant_clean_name": "Apple",
            "confidence": 0.97,
            "tags": ["electronics", "digital", "subscription"],
            "reasoning": "Tier 1 rule: Apple services match",
        },
    ),
    (
        re.compile(r"\b(google(?:\s*services|\s*play|\s*cloud)?)\b", re.IGNORECASE),
        {
            "category": "Digital Services",
            "subcategory": "Subscriptions",
            "merchant_clean_name": "Google",
            "confidence": 0.97,
            "tags": ["technology", "subscription"],
            "reasoning": "Tier 1 rule: Google services match",
        },
    ),
]


class Tier1Classifier:
    """
    Tier-1 Fast Path Classifier.
    Employs pre-compiled regex matching, normalized merchant hash lookup (<5ms latency),
    and family-specific custom override learning cache.
    """

    _in_memory_family_overrides: Dict[int, Dict[str, dict]] = {}

    def __init__(self):
        self._rules = TIER1_RULES

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Strip non-alphanumeric chars and lowercase for canonical comparison."""
        if not name:
            return ""
        return re.sub(r"[^a-z0-9]", "", name.lower())

    def save_family_override(
        self,
        family_id: int,
        merchant_name: str,
        category: str,
        subcategory: Optional[str] = None,
        merchant_clean_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Saves a custom family merchant override to local memory cache and Redis.
        Enables the parental reclassification learning loop.
        """
        norm_key = self._normalize_name(merchant_name)
        if not norm_key:
            return {}

        override_data = {
            "category": category,
            "subcategory": subcategory,
            "merchant_clean_name": merchant_clean_name or merchant_name.strip(),
            "confidence": 1.0,
            "tags": ["family_learning", "custom_override"],
            "reasoning": f"Family {family_id} parental reclassification override",
            "notes": notes,
        }

        # 1. Update in-memory cache
        if family_id not in self._in_memory_family_overrides:
            self._in_memory_family_overrides[family_id] = {}
        self._in_memory_family_overrides[family_id][norm_key] = override_data

        # 2. Persist in Redis if available
        redis_client = get_redis_client()
        if redis_client:
            try:
                redis_key = f"family_overrides:{family_id}"
                redis_client.hset(redis_key, norm_key, json.dumps(override_data))
            except Exception as e:
                logger.warning(f"Could not persist family override to Redis: {e}")

        return override_data

    def get_family_override(self, family_id: int, merchant_name: str) -> Optional[dict]:
        """
        Retrieves family-specific override from in-memory cache or Redis.
        """
        if not family_id or not merchant_name:
            return None

        norm_key = self._normalize_name(merchant_name)

        # 1. Check in-memory cache
        fam_cache = self._in_memory_family_overrides.get(family_id, {})
        if norm_key in fam_cache:
            return fam_cache[norm_key]

        # Check partial/contains match in memory cache (e.g. "Local Boba Cafe #2" vs "localbobacafe")
        for stored_key, data in fam_cache.items():
            if stored_key in norm_key or (len(norm_key) >= 4 and norm_key in stored_key):
                return data

        # 2. Check Redis cache
        redis_client = get_redis_client()
        if redis_client:
            try:
                redis_key = f"family_overrides:{family_id}"
                raw = redis_client.hget(redis_key, norm_key)
                if raw:
                    data = json.loads(raw)
                    if family_id not in self._in_memory_family_overrides:
                        self._in_memory_family_overrides[family_id] = {}
                    self._in_memory_family_overrides[family_id][norm_key] = data
                    return data
                
                # Check all keys in redis hash for partial match
                all_overrides = redis_client.hgetall(redis_key)
                for k, v in all_overrides.items():
                    if k in norm_key or (len(norm_key) >= 4 and norm_key in k):
                        data = json.loads(v)
                        if family_id not in self._in_memory_family_overrides:
                            self._in_memory_family_overrides[family_id] = {}
                        self._in_memory_family_overrides[family_id][k] = data
                        return data
            except Exception as e:
                logger.warning(f"Failed to fetch family override from Redis: {e}")

        return None

    def classify(
        self,
        merchant_name: str,
        amount: float = 0.0,
        family_id: Optional[int] = None,
    ) -> Optional[dict]:
        """
        Fast-path classification (<5ms).
        1. Checks family override first if family_id is supplied.
        2. Matches standard regex patterns.
        Returns categorization dict or None.
        """
        if not merchant_name:
            return None

        # 1. Family learning overrides take highest precedence
        if family_id:
            override = self.get_family_override(family_id, merchant_name)
            if override:
                return {
                    "category": override.get("category"),
                    "subcategory": override.get("subcategory"),
                    "merchant_clean_name": override.get("merchant_clean_name", merchant_name.strip()),
                    "confidence": override.get("confidence", 1.0),
                    "tags": override.get("tags", ["family_learning", "custom_override"]),
                    "reasoning": override.get("reasoning", f"Family {family_id} custom override learning rule"),
                }

        # 2. Regex and standard merchant matching
        for pattern, data in self._rules:
            if pattern.search(merchant_name):
                return {
                    "category": data["category"],
                    "subcategory": data["subcategory"],
                    "merchant_clean_name": data["merchant_clean_name"],
                    "confidence": data["confidence"],
                    "tags": list(data["tags"]),
                    "reasoning": data["reasoning"],
                }

        return None

