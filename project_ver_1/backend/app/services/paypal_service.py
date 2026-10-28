import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from fastapi import HTTPException

from app.config import PAYPAL_BASE_URL, PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_PAYOUTS_ENABLED

REQUEST_TIMEOUT_SECONDS = 10


def _client_credentials_auth() -> tuple[str, str]:
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="PayPal API credentials are not configured.")
    return PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET


def _raise_paypal_error(response: requests.Response, operation: str) -> None:
    try:
        detail: Any = response.json()
    except ValueError:
        detail = response.text[:1000]
    raise HTTPException(status_code=502, detail={"message": f"PayPal {operation} failed", "paypal": detail})


def get_paypal_access_token() -> str:
    """Obtain an app access token using PayPal's client_credentials grant."""
    response = requests.post(
        f"{PAYPAL_BASE_URL}/v1/oauth2/token",
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "client_credentials"},
        auth=_client_credentials_auth(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        _raise_paypal_error(response, "OAuth token request")
    token = response.json().get("access_token")
    if not token:
        raise HTTPException(status_code=502, detail="PayPal OAuth response did not contain an access token.")
    return token


def exchange_authorization_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange a user-consent authorization code for a user access/refresh token."""
    response = requests.post(
        f"{PAYPAL_BASE_URL}/v1/oauth2/token",
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        auth=_client_credentials_auth(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        _raise_paypal_error(response, "authorization code exchange")
    return response.json()


def refresh_user_access_token(refresh_token: str) -> dict[str, Any]:
    """Refresh a PayPal user-consented OAuth token."""
    response = requests.post(
        f"{PAYPAL_BASE_URL}/v1/oauth2/token",
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=_client_credentials_auth(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        _raise_paypal_error(response, "token refresh")
    return response.json()


def execute_payout(
    recipient_email: str,
    amount: Decimal | float | str,
    currency: str = "USD",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create a PayPal Payouts v1 batch. Caller supplies a stable retry key."""
    if not PAYPAL_PAYOUTS_ENABLED:
        raise HTTPException(status_code=503, detail="PayPal Payouts are disabled. Set PAYPAL_PAYOUTS_ENABLED=true after verifying the configured environment and recipient.")
    try:
        payout_amount = Decimal(str(amount))
    except InvalidOperation as exc:
        raise HTTPException(status_code=422, detail="Invalid payout amount.") from exc
    if payout_amount <= 0 or not payout_amount.is_finite():
        raise HTTPException(status_code=422, detail="Payout amount must be positive and finite.")
    if currency != "USD":
        raise HTTPException(status_code=422, detail="Version 1 payouts support USD only.")
    if not recipient_email.strip():
        raise HTTPException(status_code=422, detail="A recipient email is required.")

    request_key = idempotency_key or str(uuid.uuid4())
    response = requests.post(
        f"{PAYPAL_BASE_URL}/v1/payments/payouts",
        headers={
            "Authorization": f"Bearer {get_paypal_access_token()}",
            "Content-Type": "application/json",
        },
        json={
            "sender_batch_header": {
                "sender_batch_id": request_key,
                "email_subject": "Your family allowance",
                "email_message": "Your scheduled family allowance has been sent.",
            },
            "items": [{
                "recipient_type": "EMAIL",
                "amount": {"value": f"{payout_amount:.2f}", "currency": currency},
                "receiver": recipient_email.strip(),
                "note": "Family allowance",
                "sender_item_id": request_key,
            }],
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code != 201:
        _raise_paypal_error(response, "Payouts API request")
    return response.json()


def verify_webhook_signature(headers: dict[str, str], body: dict[str, Any], webhook_id: str) -> bool:
    """Verify a webhook with PayPal's verify-webhook-signature endpoint."""
    required_headers = {
        "transmission_id": "paypal-transmission-id",
        "transmission_time": "paypal-transmission-time",
        "cert_url": "paypal-cert-url",
        "auth_algo": "paypal-auth-algo",
        "transmission_sig": "paypal-transmission-sig",
    }
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    if not webhook_id or any(normalized_headers.get(header) is None for header in required_headers.values()):
        return False
    payload = {field: normalized_headers[header] for field, header in required_headers.items()}
    payload.update({"webhook_id": webhook_id, "webhook_event": body})
    try:
        response = requests.post(
            f"{PAYPAL_BASE_URL}/v1/notifications/verify-webhook-signature",
            headers={"Authorization": f"Bearer {get_paypal_access_token()}", "Content-Type": "application/json"},
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return response.status_code == 200 and response.json().get("verification_status") == "SUCCESS"
    except (requests.RequestException, ValueError, HTTPException):
        return False


def search_transactions(start_date: str, end_date: str, page: int = 1, page_size: int = 100) -> dict[str, Any]:
    """Read transactions with the Transaction Search API, subject to app/account permissions."""
    if not 1 <= page_size <= 500:
        raise HTTPException(status_code=422, detail="page_size must be between 1 and 500.")
    response = requests.get(
        f"{PAYPAL_BASE_URL}/v1/reporting/transactions",
        headers={"Authorization": f"Bearer {get_paypal_access_token()}", "Content-Type": "application/json", "PayPal-Enforce-ISO8601-Format": "true"},
        params={"start_date": start_date, "end_date": end_date, "page": page, "page_size": page_size},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        _raise_paypal_error(response, "Transaction Search API request")
    return response.json()


