from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import PolicyRule, User
from app.security.auth import get_current_user, require_parent
from app.services.gemini_service import evaluate_policy

router = APIRouter(prefix="/guardrails", tags=["AI Natural Language Guardrails"])


class RuleCreate(BaseModel):
    rule_text: str = Field(min_length=3, max_length=2000)


class EvaluationRequest(BaseModel):
    merchant: str = Field(min_length=1, max_length=255)
    amount: float = Field(gt=0)
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=1000)
    currency: str = "USD"


@router.post("/rules", status_code=201)
def create_policy_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    parent: User = Depends(require_parent),
):
    if not parent.is_verified:
        raise HTTPException(status_code=403, detail="A verified parent is required to configure family policies.")
    rule = PolicyRule(family_id=parent.family_id, parent_id=parent.id, rule_text=payload.rule_text.strip())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/rules")
def list_policy_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(PolicyRule).filter(
        PolicyRule.family_id == current_user.family_id,
        PolicyRule.is_active.is_(True),
    ).all()


@router.post("/evaluate")
def evaluate_transaction_guardrails(
    payload: EvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rules = db.query(PolicyRule).filter(
        PolicyRule.family_id == current_user.family_id,
        PolicyRule.is_active.is_(True),
    ).all()
    return evaluate_policy([rule.rule_text for rule in rules], payload.model_dump())
