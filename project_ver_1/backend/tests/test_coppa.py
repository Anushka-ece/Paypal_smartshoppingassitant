from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.family import Family
from app.models.user import User, UserRole
from app.models.account import Account, AccountType
from app.security.coppa import is_coppa_minor, verify_parental_consent


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
        ],
    )

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        test_engine.dispose()


def test_coppa_age_check():
    # 2018 birthdate is well under 13 years old
    assert is_coppa_minor(date(2018, 1, 1)) is True
    # 2005 birthdate is over 18 years old
    assert is_coppa_minor(date(2005, 1, 1)) is False


def test_coppa_consent_requires_authenticated_parent_paypal(db_session):
    family = Family(name="Consent Family")
    db_session.add(family)
    db_session.commit()

    parent = User(name="Sarah Parent", email="sarah@example.com", role=UserRole.PARENT.value, family_id=family.id)
    child = User(name="Leo Child", email="leo@example.com", role=UserRole.CHILD.value, family_id=family.id)
    db_session.add_all([parent, child])
    db_session.commit()

    child_dob = date(2017, 5, 20)

    # 1. Verification fails if parent has no linked active PayPal account
    result_unlinked = verify_parental_consent(
        parent_user_id=parent.id,
        child_user_id=child.id,
        child_birthdate=child_dob,
        db=db_session,
    )
    assert result_unlinked["consent_granted"] is False
    assert "paypal" in result_unlinked["reason"].lower()

    # 2. Add linked PayPal account with encrypted token
    parent_account = Account(
        user_id=parent.id,
        family_id=family.id,
        account_type=AccountType.PAYPAL_LINKED.value,
        paypal_account_id="PAYPAL-SARAH-999",
        paypal_encrypted_token="encrypted-valid-token-12345",
    )
    db_session.add(parent_account)
    db_session.commit()

    result_verified = verify_parental_consent(
        parent_user_id=parent.id,
        child_user_id=child.id,
        child_birthdate=child_dob,
        db=db_session,
    )
    assert result_verified["consent_granted"] is True
    assert result_verified["consent_status"] == "VERIFIED_PARENTAL_CONSENT"

    db_session.refresh(child)
    assert child.coppa_consent_status == "VERIFIED_PARENTAL_CONSENT"
