from app.services.gemini_service import _evaluate_simple_rules, classify_transaction, tier1_rule_fallback


def test_tier1_classifies_known_digital_merchant():
    result = tier1_rule_fallback("Steam", "Game purchase")
    assert result["category"] == "Gaming & Entertainment"
    assert result["fallback_used"] if "fallback_used" in result else result["confidence"] >= 0.9


def test_tier1_unknown_merchant_is_low_confidence():
    result = tier1_rule_fallback("Mystery Shop", "Unknown charge")
    assert result["category"] == "General Spend"
    assert result["confidence"] <= 0.5


def test_classification_without_key_uses_rules(monkeypatch):
    import app.services.gemini_service as service
    monkeypatch.setattr(service, "GEMINI_API_KEY", "")
    assert classify_transaction("Uber", "trip", 12)["category"] == "Transport"


def test_simple_policy_fallback_flags_gaming_over_threshold():
    result = _evaluate_simple_rules(
        ["Flag any purchase over $25 on video games"],
        {"merchant": "Steam", "amount": 35, "category": "Gaming & Entertainment"},
    )
    assert result["is_flagged"] is True
    assert result["risk_level"] == "HIGH"


def test_simple_policy_fallback_fails_safe_for_unparsed_rule():
    result = _evaluate_simple_rules(["Ask me about unusual things"], {"merchant": "Shop", "amount": 10, "category": "Shopping"})
    assert result["is_flagged"] is True
    assert result["risk_level"] == "MEDIUM"
