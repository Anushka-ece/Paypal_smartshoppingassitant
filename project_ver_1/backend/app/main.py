from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.webhooks import router as webhooks_router
from app.api.transactions import router as transactions_router
from app.api.allowances import router as allowances_router
from app.api.guardrails import router as guardrails_router
from app.api.family import router as family_router
from app.models import models  # noqa: F401 - registers SQLAlchemy models
from app.middleware.cors import configure_cors
from app.middleware.security_headers import configure_security_headers
from app.config import validate_production_config

app = FastAPI(
    title="PayPal Family Budgeting API",
    version="1.0.0",
    description=(
        "Family budgeting and post-capture transaction monitoring. This service does not "
        "authorize/block off-site PayPal checkouts or automatically file disputes. "
        "Child accounts remain disabled until a reviewed parental-consent flow is integrated."
    ),
)
configure_cors(app)
configure_security_headers(app)
validate_production_config()

app.include_router(auth_router)
app.include_router(webhooks_router)
app.include_router(transactions_router)
app.include_router(allowances_router)
app.include_router(guardrails_router)
app.include_router(family_router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the AI-Powered PayPal Family Budgeting & Allowance Management Platform"}
