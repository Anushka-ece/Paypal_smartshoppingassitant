import re
from typing import Dict, List, Optional, Tuple

# Categories of high-risk / prohibited merchant entities
BLACK_LIST_CATEGORIES: List[Tuple[str, str, re.Pattern]] = [
    # 1. Crypto on-ramps & exchanges
    (
        "Crypto On-Ramp",
        "Cryptocurrency exchange or high-risk digital asset on-ramp",
        re.compile(
            r"\b(crypto|bitcoin|btc|ethereum|eth|binance|coinbase|kraken|kucoin|bybit|gemini\.com|p2p-crypto|instant-payout\.biz|bitpay|moonpay)\b",
            re.IGNORECASE,
        ),
    ),
    # 2. Gambling & Sports Betting
    (
        "Gambling & Betting",
        "Online casino, sports betting, lottery or wagering platform",
        re.compile(
            r"\b(casino|stake(?:\.com)?|bet365|draftkings|fanduel|bovada|poker|betting|1xbet|roobet|sportsbook|lottery|gambling)\b",
            re.IGNORECASE,
        ),
    ),
    # 3. Unverified game key marketplaces & predatory microtransaction scams
    (
        "Unverified Game Keys & Skin Gambling",
        "Grey-market digital game key marketplace or skin gambling platform",
        re.compile(
            r"\b(g2a(?:\.com)?|kinguin|cdkeys|eneba|gamivo|lootbox|skin-gambling|csgo-skins|vbucks-free|robux-gen|hellcase|csgomoney)\b",
            re.IGNORECASE,
        ),
    ),
    # 4. Adult & Age-Restricted
    (
        "Adult & Age-Restricted",
        "Adult content, pornography, or age-restricted substance marketplace",
        re.compile(
            r"\b(onlyfans|fansly|pornhub|xhamster|cam4|chaturbate|adult-shop|vape|e-cig|tobacco|dispensary)\b",
            re.IGNORECASE,
        ),
    ),
]


class ReputationService:
    """
    Threat Intelligence & Merchant Blacklist Service.
    Evaluates merchant names and domains against known scam databases and high-risk categories.
    """

    def __init__(self):
        self._categories = BLACK_LIST_CATEGORIES

    def check_merchant(self, merchant_name: str) -> Dict[str, Optional[object]]:
        """
        Checks merchant against blacklist.
        Returns:
            {
                "is_high_risk": bool,
                "matched_category": str | None,
                "reason": str | None
            }
        """
        if not merchant_name:
            return {"is_high_risk": False, "matched_category": None, "reason": None}

        clean_target = merchant_name.strip()
        for category_name, description, pattern in self._categories:
            if pattern.search(clean_target):
                return {
                    "is_high_risk": True,
                    "matched_category": category_name,
                    "reason": f"Matched blacklist for {description} ('{merchant_name}')",
                }

        return {
            "is_high_risk": False,
            "matched_category": None,
            "reason": None,
        }
