from fastapi import FastAPI

app = FastAPI(title="PayPal Family Budgeting API", version="1.0.0")

@app.get("/")
def read_root():
    return {"message": "Welcome to the AI-Powered PayPal Family Budgeting & Allowance Management Platform"}
