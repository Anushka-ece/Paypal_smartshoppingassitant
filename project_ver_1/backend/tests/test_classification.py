import json
import time
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User, UserRole
from app.models.account import Account, AccountType
from app.models.family import Family
from app.models.transaction import Transaction, TransactionStatus
from app.services.embedding_service import Tier1Classifier
from app.services.gemini_service import classify_transaction

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
            Account.__table__,
            Transaction.__table__,
        ],
    )

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        test_engine.dispose()


def test_tier1_fast_path_match():
    classifier = Tier1Classifier()

    # Uber
    res = classifier.classify("UBER *TRIP 1234", 18.50)
    assert res is not None
    assert res["category"] == "Transport"
    assert res["merchant_clean_name"] == "Uber"
    assert res["confidence"] >= 0.95

    # Netflix
    res_netflix = classifier.classify("NETFLIX.COM PAYMENT", 15.99)
    assert res_netflix is not None
    assert res_netflix["category"] == "Entertainment"
    assert res_netflix["merchant_clean_name"] == "Netflix"
    assert res_netflix["confidence"] >= 0.95

    # Steam
    res_steam = classifier.classify("STEAM GAMES 9821", 59.99)
    assert res_steam is not None
    assert res_steam["category"] == "Gaming"
    assert res_steam["merchant_clean_name"] == "Steam"
    assert res_steam["confidence"] >= 0.95

    # Spotify
    res_spotify = classifier.classify("SPOTIFY USA", 10.99)
    assert res_spotify is not None
    assert res_spotify["category"] == "Entertainment"
    assert res_spotify["merchant_clean_name"] == "Spotify"
    assert res_spotify["confidence"] >= 0.95

    # Amazon
    res_amazon = classifier.classify("AMZN Mktp US*123", 42.00)
    assert res_amazon is not None
    assert res_amazon["category"] == "Shopping"
    assert res_amazon["merchant_clean_name"] == "Amazon"
    assert res_amazon["confidence"] >= 0.95

    # Starbucks
    res_sbux = classifier.classify("STARBUCKS STORE #1042", 5.75)
    assert res_sbux is not None
    assert res_sbux["category"] == "Food & Dining"
    assert res_sbux["merchant_clean_name"] == "Starbucks"
    assert res_sbux["confidence"] >= 0.95


def test_tier1_latency():
    classifier = Tier1Classifier()
    start = time.perf_counter()
    iterations = 200
    for _ in range(iterations):
        classifier.classify("UBER *TRIP 1234", 18.50)
    elapsed = (time.perf_counter() - start) / iterations
    # Latency per classification must be well under 5ms (0.005s)
    assert elapsed < 0.005


def test_tier1_family_override_learning():
    classifier = Tier1Classifier()

    # Before override, an unknown merchant returns None
    res = classifier.classify("Local Boba Cafe", 6.50, family_id=101)
    assert res is None

    # Save family custom override
    classifier.save_family_override(
        family_id=101,
        merchant_name="Local Boba Cafe",
        category="Treats & Snacks",
        subcategory="Boba",
    )

    # Retrieval for family 101 returns override with top confidence
    res_override = classifier.classify("Local Boba Cafe #2", 6.50, family_id=101)
    assert res_override is not None
    assert res_override["category"] == "Treats & Snacks"
    assert res_override["subcategory"] == "Boba"
    assert res_override["confidence"] >= 0.99

    # Isolated from family 202
    res_other_family = classifier.classify("Local Boba Cafe #2", 6.50, family_id=202)
    assert res_other_family is None


def test_classify_transaction_family_override_precedence():
    # Even if merchant matches standard rule (e.g. Starbucks), family override takes precedence
    classifier = Tier1Classifier()
    classifier.save_family_override(
        family_id=55,
        merchant_name="Starbucks",
        category="School Allowance",
        subcategory="Morning Treats",
    )

    result = classify_transaction(
        merchant_name="STARBUCKS STORE #99",
        description="Morning mocha",
        amount=6.25,
        family_id=55,
    )
    assert result["category"] == "School Allowance"
    assert result["subcategory"] == "Morning Treats"


def test_gemini_flash_classification_mock():
    mock_gemini_payload = {
        "category": "Education",
        "subcategory": "Tutoring",
        "merchant_clean_name": "Kumon Math",
        "confidence": 0.92,
        "tags": ["education", "math", "tutoring"],
        "reasoning": "After-school educational and tutoring center",
    }

    with patch("app.services.gemini_service._call_gemini_llm", return_value=mock_gemini_payload):
        result = classify_transaction(
            merchant_name="KUMON LEARNING CTR 881",
            description="Monthly math learning subscription",
            amount=160.00,
        )

    assert result["category"] == "Education"
    assert result["subcategory"] == "Tutoring"
    assert result["merchant_clean_name"] == "Kumon Math"
    assert result["confidence"] == 0.92
    assert "math" in result["tags"]


def test_gemini_circuit_breaker_timeout():
    def slow_llm(*args, **kwargs):
        time.sleep(0.7)  # Exceeds 500ms timeout threshold
        return {
            "category": "Slow Category",
            "subcategory": "Slow",
            "merchant_clean_name": "Slow Merchant",
            "confidence": 0.99,
            "tags": [],
            "reasoning": "Should have timed out",
        }

    start = time.perf_counter()
    with patch("app.services.gemini_service._call_gemini_llm", side_effect=slow_llm):
        result = classify_transaction(
            merchant_name="Corner Bakery & Cafe",
            description="Coffee and cinnamon roll",
            amount=8.50,
        )
    elapsed = time.perf_counter() - start

    # Circuit breaker should trip under 600ms and return rule-based fallback
    assert elapsed < 0.65
    assert result is not None
    assert result["category"] in ["Food & Dining", "General"]
    assert "fallback" in result["reasoning"].lower() or "rule" in result["reasoning"].lower()


def test_gemini_circuit_breaker_api_error():
    with patch("app.services.gemini_service._call_gemini_llm", side_effect=RuntimeError("Gemini Quota Exceeded")):
        result = classify_transaction(
            merchant_name="CHEVRON GAS STATION 42",
            description="Fuel pump 4",
            amount=45.00,
        )

    assert result is not None
    assert result["category"] == "Transport"
    assert result["subcategory"] == "Fuel"
    assert result["confidence"] > 0.0


def test_gemini_missing_api_key_safe_fallback():
    with patch("app.services.gemini_service.GEMINI_API_KEY", ""):
        result = classify_transaction(
            merchant_name="CVS PHARMACY #1092",
            description="Prescription and medicine",
            amount=22.50,
        )
    assert result is not None
    assert result["category"] in ["Health & Wellness", "Shopping", "General"]
    assert result["confidence"] > 0.0


def test_api_get_transactions(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        family = Family(name="Smith Family")
        db_session.add(family)
        db_session.commit()

        user = User(name="John Smith", email="john@example.com", role=UserRole.PARENT.value, family_id=family.id)
        db_session.add(user)
        db_session.commit()

        account = Account(user_id=user.id, family_id=family.id, balance=500.0)
        db_session.add(account)
        db_session.commit()

        tx1 = Transaction(
            account_id=account.id,
            paypal_transaction_id="TX-1001",
            amount=15.00,
            merchant_name="UBER",
            clean_merchant_name="Uber",
            category="Transport",
            subcategory="Rideshare",
            status=TransactionStatus.REFUNDED.value,
            refund_id="REFUND-1001",
        )
        tx2 = Transaction(
            account_id=account.id,
            paypal_transaction_id="TX-1002",
            amount=25.00,
            merchant_name="NETFLIX",
            clean_merchant_name="Netflix",
            category="Entertainment",
            subcategory="Streaming",
            status=TransactionStatus.COMPLETED.value,
        )
        db_session.add_all([tx1, tx2])
        db_session.commit()

        response = client.get("/api/transactions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        tx_ids = [tx["paypal_transaction_id"] for tx in data]
        assert "TX-1001" in tx_ids
        assert "TX-1002" in tx_ids
        refunded_transaction = next(tx for tx in data if tx["paypal_transaction_id"] == "TX-1001")
        assert refunded_transaction["status"] == TransactionStatus.REFUNDED.value
        assert refunded_transaction["refund_id"] == "REFUND-1001"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_api_reclassify_transaction_and_learn_loop(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        family = Family(name="Learning Family")
        db_session.add(family)
        db_session.commit()

        user = User(name="Jane Parent", email="jane@example.com", role=UserRole.PARENT.value, family_id=family.id)
        db_session.add(user)
        db_session.commit()

        account = Account(user_id=user.id, family_id=family.id, balance=300.0)
        db_session.add(account)
        db_session.commit()

        tx = Transaction(
            account_id=account.id,
            paypal_transaction_id="TX-LEARN-01",
            amount=45.00,
            merchant_name="Neighborhood Hardware",
            category="Uncategorized",
            status=TransactionStatus.COMPLETED.value,
        )
        db_session.add(tx)
        db_session.commit()
        db_session.refresh(tx)

        # Reclassify transaction
        payload = {
            "category": "Home Improvement",
            "subcategory": "Hardware Tools",
            "notes": "Parent reclassified hardware store purchase",
        }
        response = client.post(f"/api/transactions/{tx.id}/reclassify", json=payload)
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["category"] == "Home Improvement"
        assert res_data["subcategory"] == "Hardware Tools"

        # Verify DB transaction updated
        db_session.refresh(tx)
        assert tx.category == "Home Improvement"
        assert tx.subcategory == "Hardware Tools"

        # Verify learning loop: future classification for same family uses this override
        next_tx_class = classify_transaction(
            merchant_name="Neighborhood Hardware",
            description="Purchased drill bit",
            amount=12.00,
            family_id=family.id,
        )
        assert next_tx_class["category"] == "Home Improvement"
        assert next_tx_class["subcategory"] == "Hardware Tools"

    finally:
        app.dependency_overrides.pop(get_db, None)


def test_api_reclassify_not_found(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = client.post(
            "/api/transactions/999999/reclassify",
            json={"category": "Transport"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)
