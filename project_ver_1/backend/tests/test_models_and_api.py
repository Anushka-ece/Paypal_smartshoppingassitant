from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Family, User

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_function():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_registration_and_login():
    registered = client.post("/auth/register", json={
        "family_name": "Rivera family",
        "email": "parent@example.com",
        "password": "CorrectHorseBattery!23",
    })
    assert registered.status_code == 201
    assert registered.json()["status"] == "pending_verification"
    login = client.post("/auth/login", json={"email": "parent@example.com", "password": "CorrectHorseBattery!23"})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"


def test_transactions_require_authentication():
    response = client.get("/transactions/")
    assert response.status_code == 401


def test_parent_may_create_policy_and_budget_after_verification():
    db = TestingSessionLocal()
    family = Family(name="Test family")
    db.add(family)
    db.flush()
    parent = User(family_id=family.id, email="verified@example.com", hashed_password="unused", role="parent", is_verified=True)
    db.add(parent)
    db.commit()
    db.refresh(parent)
    from app.security.auth import create_access_token
    token = create_access_token(parent)
    db.close()
    headers = {"Authorization": f"Bearer {token}"}
    rule = client.post("/guardrails/rules", json={"rule_text": "Flag video game purchases over $25"}, headers=headers)
    assert rule.status_code == 201
    budget = client.post("/allowances/budgets", json={"category_name": "Gaming", "allocated_amount": "50.00"}, headers=headers)
    assert budget.status_code == 201
    assert budget.json()["currency"] == "USD"


def test_parent_cannot_create_child_without_verified_consent():
    db = TestingSessionLocal()
    family = Family(name="Unverified family")
    db.add(family)
    db.flush()
    parent = User(family_id=family.id, email="pending@example.com", hashed_password="unused", role="parent", is_verified=False)
    db.add(parent)
    db.commit()
    token = __import__("app.security.auth", fromlist=["create_access_token"]).create_access_token(parent)
    db.close()
    response = client.post("/family/invitations", json={"email": "child@example.com", "role": "child"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_parent_cannot_create_unusable_coparent_invite():
    db = TestingSessionLocal()
    family = Family(name="Invite family")
    db.add(family)
    db.flush()
    parent = User(family_id=family.id, email="inviteparent@example.com", hashed_password="unused", role="parent", is_verified=True)
    db.add(parent)
    db.commit()
    token = __import__("app.security.auth", fromlist=["create_access_token"]).create_access_token(parent)
    db.close()
    response = client.post("/family/invitations", json={"email": "coparent@example.com", "role": "parent"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 501
