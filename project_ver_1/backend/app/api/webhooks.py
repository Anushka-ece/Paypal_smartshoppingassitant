from fastapi import APIRouter

router = APIRouter(prefix="/webhooks", tags=["PayPal Webhooks"])

@router.post("/paypal")
def handle_paypal_webhook(payload: dict):
    # Handles payment captures, refunds, disputes
    return {"status": "received"}
