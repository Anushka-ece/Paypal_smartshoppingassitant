from fastapi import FastAPI
from app.api import auth, webhooks, transactions, guardrails, budgets, allowances, purchase_requests, family
from app.config import validate_production_config
from app.middleware.cors import configure_cors
from app.middleware.security_headers import configure_security_headers

validate_production_config()

app = FastAPI(title="PayPal Family Budgeting API", version="1.0.0")

# Security & CORS middleware
configure_cors(app)
configure_security_headers(app)

# Register Auth & OAuth routes
app.include_router(auth.router, prefix="/api")
app.include_router(auth.router)

# Register Family routes
app.include_router(family.router, prefix="/api")
app.include_router(family.router)

# Register Webhook routes
app.include_router(webhooks.router, prefix="/api")
app.include_router(webhooks.router)

# Register Transactions routes
app.include_router(transactions.router, prefix="/api")
app.include_router(transactions.router)

# Register Guardrails routes
app.include_router(guardrails.router, prefix="/api")
app.include_router(guardrails.router)

# Register Budgets routes
app.include_router(budgets.router, prefix="/api")
app.include_router(budgets.router)

# Register Allowances routes
app.include_router(allowances.router, prefix="/api")
app.include_router(allowances.router)

# Register Purchase Requests routes
app.include_router(purchase_requests.router, prefix="/api")
app.include_router(purchase_requests.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the AI-Powered PayPal Family Budgeting & Allowance Management Platform"}
