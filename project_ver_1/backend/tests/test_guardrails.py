import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.family import Family
from app.models.user import User, UserRole
from app.models.policy import FamilyPolicy
from app.services.reputation_service import ReputationService
from app.services.gemini_service import evaluate_policy

client = TestClient(app)


@pytest.fixture
def db_session():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    Base.metadata.create_all(
        bind=test_engine,
        tables=[
            Family.__table__,
            User.__table__,
            FamilyPolicy.__table__,
        ],
    )

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        test_engine.dispose()


def test_reputation_blacklist_detection():
    service = ReputationService()

    # Crypto on-ramp
    result_crypto = service.check_merchant("crypto-instant-payout.biz")
    assert result_crypto["is_high_risk"] is True
    assert "crypto" in result_crypto["matched_category"].lower()

    # Gambling
    result_gambling = service.check_merchant("Stake Casino & Poker")
    assert result_gambling["is_high_risk"] is True
    assert "gambling" in result_gambling["matched_category"].lower()

    # Unverified game key / digital black market
    result_keys = service.check_merchant("G2A Marketplace Digital")
    assert result_keys["is_high_risk"] is True
    assert "unverified" in result_keys["matched_category"].lower() or "keys" in result_keys["matched_category"].lower()

    # Safe merchant
    result_safe = service.check_merchant("Starbucks Coffee")
    assert result_safe["is_high_risk"] is False
    assert result_safe["matched_category"] is None


def test_evaluate_policy_threat_blacklist_priority():
    rules = ["Flag purchases over $50"]
    tx = {
        "merchant_name": "crypto-instant-payout.biz",
        "amount": 10.00,
        "category": "Finance",
        "description": "Token swap",
    }
    result = evaluate_policy(rules=rules, transaction_data=tx)
    assert result["is_flagged"] is True
    assert result["risk_level"] == "HIGH"
    assert result["requires_immediate_action"] is True
    assert "crypto" in result["summary_for_parent"].lower() or "threat" in result["summary_for_parent"].lower()


def test_evaluate_policy_mock_gemini():
    rules = ["Flag any gaming purchase over $25"]
    tx = {
        "merchant_name": "Epic Games",
        "amount": 49.99,
        "category": "Gaming",
        "description": "V-Bucks bundle pack",
    }
    mock_llm_response = {
        "is_flagged": True,
        "risk_level": "HIGH",
        "matched_rules": ["Flag any gaming purchase over $25"],
        "summary_for_parent": "Epic Games purchase of $49.99 exceeds the $25 gaming limit.",
        "requires_immediate_action": True,
    }

    with patch("app.services.gemini_service._call_gemini_policy_llm", return_value=mock_llm_response):
        result = evaluate_policy(rules=rules, transaction_data=tx)

    assert result["is_flagged"] is True
    assert result["risk_level"] == "HIGH"
    assert "exceeds" in result["summary_for_parent"].lower()


def test_evaluate_policy_fallback_keyword_and_limits():
    rules = [
        "Flag any purchase over $30",
        "Flag video games",
    ]
    # Test fallback rule engine
    with patch("app.services.gemini_service._call_gemini_policy_llm", side_effect=RuntimeError("Quota exceeded")):
        result = evaluate_policy(
            rules=rules,
            transaction_data={
                "merchant_name": "PlayStation Store",
                "amount": 35.00,
                "category": "Gaming",
                "description": "Console digital download",
            },
        )
    assert result["is_flagged"] is True
    assert result["risk_level"] in ["HIGH", "MEDIUM"]
    assert len(result["matched_rules"]) > 0


def test_guardrails_crud_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        family = Family(name="Shield Family")
        db_session.add(family)
        db_session.commit()

        # Create policy
        resp = client.post(
            "/api/guardrails",
            json={
                "family_id": family.id,
                "rule_text": "Flag any purchase over $25 on video games",
            },
        )
        assert resp.status_code == 200
        policy_data = resp.json()
        assert policy_data["id"] is not None
        assert policy_data["rule_text"] == "Flag any purchase over $25 on video games"
        assert policy_data["is_active"] is True

        # List policies
        list_resp = client.get(f"/api/guardrails?family_id={family.id}")
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert len(items) == 1

        # Toggle policy
        toggle_resp = client.put(f"/api/guardrails/{policy_data['id']}/toggle")
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["is_active"] is False

        # Delete policy
        del_resp = client.delete(f"/api/guardrails/{policy_data['id']}")
        assert del_resp.status_code == 200

        # Verify deletion
        list_resp_after = client.get(f"/api/guardrails?family_id={family.id}")
        assert len(list_resp_after.json()) == 0
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_guardrails_simulator_api():
    payload = {
        "rules": ["Flag any in-game purchases over $15"],
        "transaction": {
            "merchant_name": "Roblox Store",
            "amount": 25.00,
            "category": "Gaming",
            "description": "Robux pack",
        },
    }
    resp = client.post("/api/guardrails/simulate", json=payload)
    assert resp.status_code == 200
    res = resp.json()
    assert res["is_flagged"] is True
    assert res["risk_level"] in ["HIGH", "MEDIUM"]
    assert "summary_for_parent" in res
