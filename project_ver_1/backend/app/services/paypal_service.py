import json
import math
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, List, Tuple
from urllib.parse import urlparse
import httpx
from app.config import (
    APP_ENV,
    PAYPAL_BASE_URL,
    PAYPAL_CLIENT_ID,
    PAYPAL_CLIENT_SECRET,
    PAYPAL_ALLOW_MOCK_WEBHOOKS,
    PAYPAL_PAYOUTS_ENABLED,
    PAYPAL_REDIRECT_URI,
    PAYPAL_WEBHOOK_ID,
)
from app.security.crypto import decrypt_token


class AwaitableList(list):
    """
    List subclass that can be returned synchronously or awaited in async contexts.
    Allows seamless usage for both Celery (sync) and FastAPI/asyncio callers.
    """
    def __await__(self):
        async def _coro():
            return self
        return _coro().__await__()


class PayPalService:
    _token_cache: Dict[Tuple[str, str], Tuple[str, float]] = {}

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
        webhook_id: Optional[str] = None,
    ):
        self.client_id = client_id or PAYPAL_CLIENT_ID
        self.client_secret = client_secret or PAYPAL_CLIENT_SECRET
        self.base_url = (base_url or PAYPAL_BASE_URL).rstrip("/")
        self.webhook_id = webhook_id or PAYPAL_WEBHOOK_ID
        self._app_access_token: Optional[str] = None
        self._app_access_token_expires_at = 0.0


    def get_authorization_url(
        self,
        redirect_uri: Optional[str] = None,
        state: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> str:
        """Constructs the PayPal OAuth 2.0 authorization URL."""
        self._require_sandbox_api()
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
        self._require_sandbox_api()
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
        if not isinstance(refresh_token, str) or not refresh_token.strip():
            raise ValueError("A PayPal refresh token is required.")
        self._require_sandbox_api()
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
        self._require_sandbox_api()
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

    async def get_app_access_token(self) -> str:
        """Fetches an application-level access token via client credentials grant."""
        self._require_sandbox_api()
        cache_key = (self.base_url, self.client_id)
        now = time.monotonic()
        cached = self._token_cache.get(cache_key)
        if cached and cached[1] > now:
            self._app_access_token, self._app_access_token_expires_at = cached
            return self._app_access_token

        if not self.client_id or not self.client_secret:
            raise RuntimeError("PayPal client credentials are not configured.")

        token_url = f"{self.base_url}/v1/oauth2/token"
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }
        data = {"grant_type": "client_credentials"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                token_url,
                auth=(self.client_id, self.client_secret),
                headers=headers,
                data=data,
                timeout=10.0,
            )
            resp.raise_for_status()
            token_payload = resp.json()
            access_token = token_payload.get("access_token")
            if not access_token:
                raise RuntimeError("PayPal OAuth response did not contain an access token.")

            expires_in = token_payload.get("expires_in")
            if isinstance(expires_in, (int, float)) and expires_in > 0:
                cache_ttl = expires_in - min(60.0, expires_in * 0.1)
                self._app_access_token_expires_at = now + cache_ttl
                self._token_cache[cache_key] = (
                    access_token,
                    self._app_access_token_expires_at,
                )
            else:
                self._app_access_token_expires_at = 0.0
                self._token_cache.pop(cache_key, None)

            self._app_access_token = access_token
            return access_token

    async def get_access_token(self) -> Dict[str, Any]:
        """Compatibility wrapper returning the token payload shape expected by callers."""
        return {"access_token": await self.get_app_access_token()}

    async def verify_webhook_signature(
        self,
        headers: Dict[str, Any],
        body: Union[bytes, str, Dict[str, Any]],
        webhook_id: Optional[str] = None,
    ) -> bool:
        """
        Verifies the PayPal webhook signature against PayPal's verification endpoint.
        Supports mock/sandbox signature bypass when configured with mock webhook ID or test headers.
        """
        headers_lower = {str(k).lower(): str(v) for k, v in headers.items()}
        auth_algo = headers_lower.get("paypal-auth-algo")
        cert_url = headers_lower.get("paypal-cert-url")
        transmission_id = headers_lower.get("paypal-transmission-id")
        transmission_sig = headers_lower.get("paypal-transmission-sig")
        transmission_time = headers_lower.get("paypal-transmission-time")

        if not all([auth_algo, cert_url, transmission_id, transmission_sig, transmission_time]):
            return False

        # Parse body
        if isinstance(body, bytes):
            try:
                webhook_event = json.loads(body.decode("utf-8"))
            except Exception:
                return False
        elif isinstance(body, str):
            try:
                webhook_event = json.loads(body)
            except Exception:
                return False
        elif isinstance(body, dict):
            webhook_event = body
        else:
            return False

        target_webhook_id = webhook_id or self.webhook_id or PAYPAL_WEBHOOK_ID

        # Mock / Sandbox verification check
        is_mock_webhook = target_webhook_id in (
            "mock_webhook_id",
            "mock",
            "test_webhook_id",
            "mock-webhook-id",
        )
        is_mock_sig = (
            transmission_sig.startswith("mock-")
            or transmission_sig in ("valid_signature", "valid-signature", "mock-valid-signature")
        )

        if (
            PAYPAL_ALLOW_MOCK_WEBHOOKS
            and APP_ENV.lower() in {"local", "development", "test"}
            and (is_mock_webhook or is_mock_sig)
        ):
            if transmission_sig in ("mock-invalid", "invalid-signature", "invalid", "mock-invalid-sig") or auth_algo == "INVALID":
                return False
            return True

        # PayPal API Verification
        try:
            paypal_host = urlparse(self.base_url)
            if (
                paypal_host.scheme != "https"
                or paypal_host.hostname
                not in {"api-m.sandbox.paypal.com", "api-m.paypal.com"}
            ):
                return False
            access_token = await self.get_app_access_token()
            verify_url = f"{self.base_url}/v1/notifications/verify-webhook-signature"
            verify_payload = {
                "auth_algo": auth_algo,
                "cert_url": cert_url,
                "transmission_id": transmission_id,
                "transmission_sig": transmission_sig,
                "transmission_time": transmission_time,
                "webhook_id": target_webhook_id,
                "webhook_event": webhook_event,
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    verify_url,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Authorization": f"Bearer {access_token}",
                    },
                    json=verify_payload,
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    res_data = resp.json()
                    return res_data.get("verification_status") == "SUCCESS"
                return False
        except Exception:
            return False

    @staticmethod
    def parse_transaction_record(raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses a transaction record from PayPal Reporting API (/v1/reporting/transactions)
        or normalized dictionary format into standard internal fields:
        transaction_id, amount, currency, merchant_name, status, initiation_date, description.
        """
        tx_info = raw_record.get("transaction_info") or raw_record
        payer_info = raw_record.get("payer_info") or {}
        cart_info = raw_record.get("cart_info") or {}

        # 1. Transaction ID
        transaction_id = (
            tx_info.get("transaction_id")
            or raw_record.get("transaction_id")
            or tx_info.get("id")
            or raw_record.get("id")
        )

        # 2. Amount and Currency
        raw_amount_obj = tx_info.get("transaction_amount")
        if isinstance(raw_amount_obj, dict):
            amount_val = raw_amount_obj.get("value", 0.0)
            currency = raw_amount_obj.get("currency_code", "USD")
        elif raw_amount_obj is not None:
            amount_val = raw_amount_obj
            currency = tx_info.get("currency") or raw_record.get("currency", "USD")
        else:
            amount_val = raw_record.get("amount", 0.0)
            currency = raw_record.get("currency", "USD")

        try:
            amount = abs(float(amount_val))
        except (ValueError, TypeError):
            amount = 0.0

        # 3. Merchant Name
        merchant_name = None
        payer_name = payer_info.get("payer_name")
        if isinstance(payer_name, dict):
            merchant_name = (
                payer_name.get("alternate_full_name")
                or f"{payer_name.get('given_name', '')} {payer_name.get('surname', '')}".strip()
            )
        elif isinstance(payer_name, str):
            merchant_name = payer_name

        if not merchant_name:
            merchant_name = payer_info.get("email_address")

        if (
            not merchant_name
            and isinstance(cart_info.get("item_details"), list)
            and len(cart_info["item_details"]) > 0
        ):
            first_item = cart_info["item_details"][0]
            if isinstance(first_item, dict):
                merchant_name = first_item.get("item_name")

        if not merchant_name:
            merchant_name = (
                tx_info.get("transaction_subject")
                or tx_info.get("transaction_note")
                or raw_record.get("merchant_name")
                or "PayPal Merchant"
            )

        # 4. Status mapping
        raw_status = (
            tx_info.get("transaction_status")
            or raw_record.get("status")
            or "COMPLETED"
        )
        status_map = {
            "S": "COMPLETED",
            "SUCCESS": "COMPLETED",
            "COMPLETED": "COMPLETED",
            "P": "PENDING",
            "PENDING": "PENDING",
            "D": "DENIED",
            "DENIED": "DENIED",
            "V": "REFUNDED",
            "REVERSED": "REFUNDED",
            "REFUNDED": "REFUNDED",
            "F": "FAILED",
            "FAILED": "FAILED",
        }
        status = status_map.get(str(raw_status).upper(), str(raw_status))

        # 5. Initiation Date
        initiation_date = (
            tx_info.get("transaction_initiation_date")
            or tx_info.get("transaction_updated_date")
            or raw_record.get("initiation_date")
            or raw_record.get("created_at")
        )
        if not initiation_date:
            initiation_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        # 6. Description
        description = (
            tx_info.get("transaction_note")
            or tx_info.get("transaction_subject")
            or raw_record.get("description")
            or f"PayPal purchase: {merchant_name}"
        )

        return {
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": currency,
            "merchant_name": merchant_name,
            "status": status,
            "raw_status": raw_status,
            "initiation_date": str(initiation_date),
            "description": description,
            "raw_record": raw_record,
        }

    def fetch_historical_transactions(
        self,
        access_token: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page_size: int = 100,
    ) -> AwaitableList:
        """
        Fetches historical transactions from PayPal's Reporting API (/v1/reporting/transactions).
        Handles pagination, automatic mock fallback, and parsed record mapping.
        Callable synchronously or awaitable in async contexts.
        """
        self._require_sandbox_api()
        raw_token = access_token
        try:
            raw_token = decrypt_token(access_token)
        except Exception:
            raw_token = access_token

        is_mock = (
            not raw_token
            or raw_token.startswith("mock")
            or raw_token.startswith("test")
            or self.client_id in ("mock_client_id", "mock", "test")
        )

        if is_mock:
            now = datetime.utcnow()
            mock_records = [
                {
                    "transaction_id": "TX-MOCK-001",
                    "amount": 45.00,
                    "currency": "USD",
                    "merchant_name": "Steam Games",
                    "status": "COMPLETED",
                    "initiation_date": (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "description": "Steam Games digital purchase",
                },
                {
                    "transaction_id": "TX-MOCK-002",
                    "amount": 18.50,
                    "currency": "USD",
                    "merchant_name": "Uber",
                    "status": "COMPLETED",
                    "initiation_date": (now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "description": "Uber ride",
                },
                {
                    "transaction_id": "TX-MOCK-003",
                    "amount": 12.99,
                    "currency": "USD",
                    "merchant_name": "Netflix",
                    "status": "COMPLETED",
                    "initiation_date": (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "description": "Netflix monthly subscription",
                },
                {
                    "transaction_id": "TX-MOCK-004",
                    "amount": 89.20,
                    "currency": "USD",
                    "merchant_name": "Amazon",
                    "status": "COMPLETED",
                    "initiation_date": (now - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "description": "Amazon online shopping",
                },
            ]
            return AwaitableList(mock_records)

        now = datetime.utcnow()
        if not end_date:
            end_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        if not start_date:
            start_date = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"{self.base_url}/v1/reporting/transactions"
        headers = {
            "Authorization": f"Bearer {raw_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        all_transactions = []
        page = 1
        with httpx.Client(timeout=20.0) as client:
            while True:
                params = {
                    "start_date": start_date,
                    "end_date": end_date,
                    "page_size": page_size,
                    "page": page,
                    "fields": "all",
                }
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                details = data.get("transaction_details", [])
                for item in details:
                    parsed = self.parse_transaction_record(item)
                    all_transactions.append(parsed)

                total_pages = data.get("total_pages", 1)
                if page >= total_pages or not details:
                    break
                page += 1

        return AwaitableList(all_transactions)

    async def fetch_historical_transactions_async(
        self,
        access_token: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """Asynchronous wrapper for fetch_historical_transactions."""
        return self.fetch_historical_transactions(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            page_size=page_size,
        )



    async def execute_payout(
        self,
        receiver_email: str,
        amount: float,
        idempotency_key: str,
        currency: str = "USD",
        note: str = "Automated Family Allowance Disbursement",
    ) -> Dict[str, Any]:
        """
        Executes a PayPal Payout (POST /v1/payments/payouts) with idempotency key.
        """
        self._require_sandbox_api()
        if not receiver_email or not idempotency_key or not math.isfinite(amount) or amount <= 0:
            raise ValueError("A valid receiver, positive payout amount, and idempotency key are required.")
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise ValueError("PayPal payout currency must be a three-letter ISO currency code.")
        currency = currency.upper()
        if not PAYPAL_PAYOUTS_ENABLED:
            raise RuntimeError("PayPal payouts are disabled. Set PAYPAL_PAYOUTS_ENABLED=true to enable them.")

        url = f"{self.base_url}/v1/payments/payouts"
        token_info = await self.get_access_token()
        token = token_info.get("access_token", "")
        if not token:
            raise RuntimeError("PayPal did not provide an access token for the payout.")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": idempotency_key,
        }

        payload = {
            "sender_batch_header": {
                "sender_batch_id": f"batch-{idempotency_key}",
                "email_subject": "You have an allowance payout!",
                "email_message": note,
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "amount": {"value": f"{amount:.2f}", "currency": currency},
                    "note": note,
                    "sender_item_id": f"item-{idempotency_key}",
                    "receiver": receiver_email,
                }
            ],
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return {
                "batch_id": data.get("batch_header", {}).get("payout_batch_id"),
                "status": data.get("batch_header", {}).get("batch_status", "PENDING"),
                "receiver": receiver_email,
                "amount": amount,
                "currency": currency,
                "idempotency_key": idempotency_key,
            }

    async def create_order_for_approval(
        self,
        amount: float,
        currency: str = "USD",
        description: str = "Family Pre-Purchase Request",
        request_id: Optional[int] = None,
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a sandbox PayPal Order and returns its approval link."""
        self._require_sandbox_api()
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("PayPal order amount must be a positive finite number.")
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise ValueError("PayPal order currency must be a three-letter ISO currency code.")
        currency = currency.upper()
        if not return_url or not cancel_url:
            raise ValueError("PayPal return and cancellation URLs are required.")

        url = f"{self.base_url}/v2/checkout/orders"
        token_info = await self.get_access_token()
        token = token_info.get("access_token", "")
        if not token:
            raise RuntimeError("PayPal did not provide an access token for the order.")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if request_id is not None:
            headers["PayPal-Request-Id"] = f"purchase-order-{request_id}"
        purchase_unit = {
            "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
            "description": description,
        }
        if request_id is not None:
            purchase_unit["custom_id"] = f"purchase-request-{request_id}"
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [purchase_unit],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
                "user_action": "PAY_NOW",
            },
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def capture_approved_order(
        self, order_id: str, request_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Captures a PayPal-approved sandbox order idempotently."""
        self._require_sandbox_api()

        url = f"{self.base_url}/v2/checkout/orders/{order_id}/capture"
        token_info = await self.get_access_token()
        token = token_info.get("access_token", "")
        if not token:
            raise RuntimeError("PayPal did not provide an access token for the capture.")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if request_id is not None:
            headers["PayPal-Request-Id"] = f"purchase-capture-{request_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def _require_sandbox_api(self) -> None:
        if urlparse(self.base_url).hostname != "api-m.sandbox.paypal.com":
            raise RuntimeError("PayPal payment operations are restricted to the sandbox API.")
        if not self.client_id or not self.client_secret:
            raise RuntimeError("PayPal client credentials are not configured.")


# Legacy helper placeholders
def get_paypal_access_token():
    service = PayPalService()
    return service


def execute_payout(recipient_email: str, amount: float, currency: str = "USD"):
    service = PayPalService()
    return service.execute_payout(
        receiver_email=recipient_email,
        amount=amount,
        idempotency_key=f"legacy-{int(time.time())}",
        currency=currency,
    )
