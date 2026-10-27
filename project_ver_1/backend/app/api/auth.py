from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Authentication & PayPal OAuth"])

@router.get("/login")
def paypal_login():
    return {"auth_url": "https://www.sandbox.paypal.com/signin/authorize?... "}
