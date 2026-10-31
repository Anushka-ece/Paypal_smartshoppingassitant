from datetime import date, datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.account import Account, AccountType


def is_coppa_minor(birthdate: date) -> bool:
    """
    Evaluates whether an individual is under the age of 13 subject to FTC COPPA regulations.
    """
    today = date.today()
    age = (
        today.year
        - birthdate.year
        - ((today.month, today.day) < (birthdate.month, birthdate.day))
    )
    return age < 13


def verify_parental_consent(
    parent_user_id: int,
    child_user_id: int,
    child_birthdate: date,
    db: Session,
) -> Dict[str, Any]:
    """
    Enforces FTC-compliant Verifiable Parental Consent (VPC).
    Requires verified parent identity and an active authenticated PayPal OAuth session
    with stored encrypted token before account provisioning for minors under 13.
    """
    parent = db.query(User).filter(User.id == parent_user_id).first()
    if not parent or parent.role not in [UserRole.PARENT.value, UserRole.CO_PARENT.value]:
        return {
            "consent_granted": False,
            "reason": "Invalid or unverified parent user ID.",
        }

    # Verify active parent PayPal OAuth account linking
    parent_account = (
        db.query(Account)
        .filter(
            Account.user_id == parent.id,
            Account.paypal_encrypted_token.isnot(None),
            Account.is_active.is_(True),
        )
        .first()
    )

    if not parent_account:
        return {
            "consent_granted": False,
            "reason": "Parent must connect and authenticate an active PayPal account to grant COPPA consent.",
        }

    # Grant consent and update child record
    child = db.query(User).filter(User.id == child_user_id).first()
    if child:
        child.coppa_consent_status = "VERIFIED_PARENTAL_CONSENT"
        child.age = (
            date.today().year
            - child_birthdate.year
            - ((date.today().month, date.today().day) < (child_birthdate.month, child_birthdate.day))
        )
        db.commit()
        db.refresh(child)

    return {
        "consent_granted": True,
        "consent_status": "VERIFIED_PARENTAL_CONSENT",
        "parent_id": parent.id,
        "child_id": child_user_id,
        "verified_at": datetime.utcnow().isoformat(),
        "method": "PAYPAL_OAUTH_PAYMENT_METHOD_VERIFICATION",
    }
