from fastapi import FastAPI
from app.api import auth, webhooks, transactions, guardrails

app = FastAPI(title="PayPal Family Budgeting API", version="1.0.0")

# Register Auth & OAuth routes
app.include_router(auth.router, prefix="/api")
app.include_router(auth.router)

# Register Webhook routes
app.include_router(webhooks.router, prefix="/api")
app.include_router(webhooks.router)

# Register Transactions routes
app.include_router(transactions.router, prefix="/api")
app.include_router(transactions.router)

# Register Guardrails routes
app.include_router(guardrails.router, prefix="/api")
app.include_router(guardrails.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the AI-Powered PayPal Family Budgeting & Allowance Management Platform"}
