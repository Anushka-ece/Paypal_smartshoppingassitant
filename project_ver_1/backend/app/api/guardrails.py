from fastapi import APIRouter

router = APIRouter(prefix="/guardrails", tags=["AI Natural Language Guardrails"])

@router.post("/evaluate")
def evaluate_transaction():
    return {"is_flagged": False, "risk_level": "LOW"}
