from fastapi import APIRouter

router = APIRouter(prefix="/transactions", tags=["Transactions & LLM Categorization"])

@router.get("/")
def get_transactions():
    return []
