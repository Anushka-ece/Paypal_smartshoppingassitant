from fastapi import APIRouter

router = APIRouter(prefix="/allowances", tags=["Allowances & Budgets"])

@router.get("/")
def get_allowances():
    return []
