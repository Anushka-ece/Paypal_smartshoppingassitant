import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.policy import FamilyPolicy
from app.models.user import User
from app.security.auth import get_current_user, require_family_member, require_family_parent
from app.services.gemini_service import evaluate_policy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/guardrails", tags=["AI Natural Language Guardrails"])


class PolicyCreate(BaseModel):
    family_id: int
    rule_text: str


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    rule_text: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SimulateRequest(BaseModel):
    rules: List[str]
    transaction: Dict[str, object]


class EvaluateRequest(BaseModel):
    family_id: int
    transaction: Dict[str, object]


class GuardrailEvaluationResponse(BaseModel):
    is_flagged: bool
    risk_level: str
    matched_rules: List[str]
    summary_for_parent: str
    requires_immediate_action: bool


@router.get("", response_model=List[PolicyResponse])
@router.get("/", response_model=List[PolicyResponse])
def list_policies(
    family_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active and inactive policies for a family."""
    require_family_member(current_user, family_id)
    policies = (
        db.query(FamilyPolicy)
        .filter(FamilyPolicy.family_id == family_id)
        .order_by(FamilyPolicy.created_at.desc())
        .all()
    )
    return policies


@router.post("", response_model=PolicyResponse)
@router.post("/", response_model=PolicyResponse)
def create_policy(
    payload: PolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new natural language guardrail policy."""
    require_family_parent(current_user, payload.family_id)
    if not payload.rule_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rule text cannot be empty.",
        )

    policy = FamilyPolicy(
        family_id=payload.family_id,
        rule_text=payload.rule_text.strip(),
        is_active=True,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.put("/{policy_id}/toggle", response_model=PolicyResponse)
def toggle_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle active/inactive state of a guardrail rule."""
    policy = (
        db.query(FamilyPolicy)
        .filter(FamilyPolicy.id == policy_id, FamilyPolicy.family_id == current_user.family_id)
        .first()
    )
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy {policy_id} not found",
        )
    require_family_parent(current_user, policy.family_id)
    policy.is_active = not policy.is_active
    db.commit()
    db.refresh(policy)
    return policy


@router.delete("/{policy_id}")
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a guardrail rule."""
    policy = (
        db.query(FamilyPolicy)
        .filter(FamilyPolicy.id == policy_id, FamilyPolicy.family_id == current_user.family_id)
        .first()
    )
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy {policy_id} not found",
        )
    require_family_parent(current_user, policy.family_id)
    db.delete(policy)
    db.commit()
    return {"message": f"Policy {policy_id} deleted successfully."}


@router.post("/simulate", response_model=GuardrailEvaluationResponse)
def simulate_guardrails(
    payload: SimulateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Interactive rule testing simulator:
    Evaluates draft rules against sample transaction metadata without persisting to database.
    """
    result = evaluate_policy(rules=payload.rules, transaction_data=payload.transaction)
    return result


@router.post("/evaluate", response_model=GuardrailEvaluationResponse)
def evaluate_transaction_guardrails(
    payload: EvaluateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Evaluates a transaction against all active family policies.
    """
    require_family_member(current_user, payload.family_id)
    active_policies = (
        db.query(FamilyPolicy)
        .filter(FamilyPolicy.family_id == payload.family_id, FamilyPolicy.is_active.is_(True))
        .all()
    )
    rules = [p.rule_text for p in active_policies]
    result = evaluate_policy(rules=rules, transaction_data=payload.transaction)
    return result
