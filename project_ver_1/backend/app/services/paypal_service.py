import urllib.parse
from typing import Optional, Dict, Any
import httpx
from app.config import (
    PAYPAL_BASE_URL,
    PAYPAL_CLIENT_ID,
    PAYPAL_CLIENT_SECRET,
    PAYPAL_REDIRECT_URI,
)
from app.security.crypto import decrypt_token


class PayPalService:
    SUPPORTED_WEBHOOK_EVENTS = {
        "PAYMENT.CAPTURE.COMPLETED",
        "PAYMENT.CAPTURE.REFUNDED",
        "PAYMENT.SALE.REFUNDED",
        "CUSTOMER.DISPUTE.RESOLVED",
    }

    DEFAULT_SCOPES = (
        "openid profile email "
        "https://uri.paypal.com/services/wallet/financial-instruments "
        "https://uri.paypal.com/services/payments/realtimepayment "
        "https://uri.paypal.com/services/disputes/read "
        "https://uri.paypal.com/services/reporting/search/read"
    )

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.client_id = client_id or PAYPAL_CLIENT_ID
        self.client_secret = client_secret or PAYPAL_CLIENT_SECRET
        self.base_url = (base_url or PAYPAL_BASE_URL).rstrip("/")

    def get_authorization_url(
        self,
        redirect_uri: Optional[str] = None,
        state: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> str:
        """Constructs the PayPal OAuth 2.0 authorization URL."""
        if "sandbox" in self.base_url.lower():
            auth_base = "https://www.sandbox.paypal.com/signin/authorize"
        else:
            auth_base = "https://www.paypal.com/signin/authorize"

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": scope or self.DEFAULT_SCOPES,
            "redirect_uri": redirect_uri or PAYPAL_REDIRECT_URI,
        }
        if state:
            params["state"] = state

        return f"{auth_base}?{urllib.parse.urlencode(params)}"

    async def exchange_oauth_code(
        self,
        code: str,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exchanges an authorization code for PayPal access and refresh tokens."""
        token_url = f"{self.base_url}/v1/oauth2/token"
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }
        data = {
            "grant_type": "authorization_code",
            "code": code,
        }
        if redirect_uri:
            data["redirect_uri"] = redirect_uri

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                token_url,
                auth=(self.client_id, self.client_secret),
                headers=headers,
                data=data,
            )
            resp.raise_for_status()
            return resp.json()

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refreshes an access token using a refresh token.
        Accepts either an encrypted refresh token (auto-decrypted) or raw refresh token string.
        """
        raw_token = refresh_token
        try:
            raw_token = decrypt_token(refresh_token)
        except Exception:
            raw_token = refresh_token

        token_url = f"{self.base_url}/v1/oauth2/token"
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": raw_token,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                token_url,
                auth=(self.client_id, self.client_secret),
                headers=headers,
                data=data,
            )
            resp.raise_for_status()
            return resp.json()

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Alias for refresh_access_token."""
        return await self.refresh_access_token(refresh_token)

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Fetches the user's PayPal identity profile using the access token."""
        userinfo_url = f"{self.base_url}/v1/identity/oauth2/userinfo?schema=paypalv1.1"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(userinfo_url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def is_event_supported(self, event_type: str) -> bool:
        """Checks if a webhook event type is supported by the ingestion engine."""
        return event_type in self.SUPPORTED_WEBHOOK_EVENTS


# Legacy helper placeholders
def get_paypal_access_token():
    service = PayPalService()
    return service


def execute_payout(recipient_email: str, amount: float, currency: str = "USD"):
    pass
