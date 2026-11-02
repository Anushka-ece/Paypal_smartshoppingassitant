from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services import paypal_service as paypal_service_module
from app.services.paypal_service import PayPalService


def _response(url, payload, status_code=200):
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("POST", url),
    )


@pytest.mark.anyio
async def test_app_access_token_cache_respects_expiry(monkeypatch):
    service = PayPalService(
        client_id="sandbox-client",
        client_secret="sandbox-secret",
        base_url="https://api-m.sandbox.paypal.com",
    )
    cache_key = (service.base_url, service.client_id)
    PayPalService._token_cache.pop(cache_key, None)
    clock = [100.0]
    monkeypatch.setattr(paypal_service_module.time, "monotonic", lambda: clock[0])
    token_url = f"{service.base_url}/v1/oauth2/token"

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=[
            _response(token_url, {"access_token": "token-one", "expires_in": 100}),
            _response(token_url, {"access_token": "token-two", "expires_in": 100}),
        ],
    ) as post:
        assert await service.get_app_access_token() == "token-one"
        assert await PayPalService(
            client_id="sandbox-client",
            client_secret="sandbox-secret",
            base_url="https://api-m.sandbox.paypal.com",
        ).get_access_token() == {"access_token": "token-one"}
        assert post.await_count == 1

        clock[0] = 191.0
        assert await service.get_app_access_token() == "token-two"
        assert post.await_count == 2

    PayPalService._token_cache.pop(cache_key, None)


@pytest.mark.anyio
async def test_order_creation_and_capture_use_sandbox_and_idempotency():
    service = PayPalService(
        client_id="sandbox-client",
        client_secret="sandbox-secret",
        base_url="https://api-m.sandbox.paypal.com",
    )
    service.get_access_token = AsyncMock(return_value={"access_token": "sandbox-token"})
    order_url = f"{service.base_url}/v2/checkout/orders"
    capture_url = f"{order_url}/ORDER-42/capture"

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=[
            _response(
                order_url,
                {
                    "id": "ORDER-42",
                    "status": "CREATED",
                    "links": [{"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow"}],
                },
            ),
            _response(
                capture_url,
                {
                    "id": "ORDER-42",
                    "status": "COMPLETED",
                    "purchase_units": [
                        {"payments": {"captures": [{"id": "CAPTURE-42"}]}}
                    ],
                },
            ),
        ],
    ) as post:
        order = await service.create_order_for_approval(
            amount=20.0,
            currency="USD",
            request_id=42,
            return_url="http://localhost:8000/return",
            cancel_url="http://localhost:8000/cancel",
        )
        captured = await service.capture_approved_order("ORDER-42", request_id=42)

    assert order["id"] == "ORDER-42"
    assert order["links"][0]["href"].startswith("https://www.sandbox.paypal.com/")
    order_call = post.call_args_list[0].kwargs
    assert order_call["headers"]["PayPal-Request-Id"] == "purchase-order-42"
    assert order_call["headers"]["Authorization"] == "Bearer sandbox-token"
    assert order_call["json"]["application_context"]["return_url"] == "http://localhost:8000/return"
    assert order_call["json"]["purchase_units"][0]["custom_id"] == "purchase-request-42"
    capture_call = post.call_args_list[1].kwargs
    assert capture_call["headers"]["PayPal-Request-Id"] == "purchase-capture-42"
    assert capture_call["headers"]["Authorization"] == "Bearer sandbox-token"
    assert captured["status"] == "COMPLETED"


@pytest.mark.anyio
async def test_payment_operations_reject_live_api_and_missing_credentials():
    live_service = PayPalService(
        client_id="client",
        client_secret="secret",
        base_url="https://api-m.paypal.com",
    )
    with pytest.raises(RuntimeError, match="sandbox"):
        await live_service.create_order_for_approval(1.0)

    unconfigured = PayPalService(
        client_id="",
        client_secret="",
        base_url="https://api-m.sandbox.paypal.com",
    )
    with pytest.raises(RuntimeError, match="credentials"):
        await unconfigured.create_order_for_approval(1.0)
    with pytest.raises(RuntimeError, match="sandbox"):
        live_service.get_authorization_url(state="oauth-state")
    with pytest.raises(ValueError, match="refresh token"):
        await unconfigured.refresh_access_token("")


@pytest.mark.anyio
async def test_mock_webhook_bypass_requires_explicit_nonproduction_setting(monkeypatch):
    service = PayPalService(webhook_id="mock_webhook_id")
    headers = {
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-cert-url": "https://api.sandbox.paypal.com/cert",
        "paypal-transmission-id": "trans-1",
        "paypal-transmission-sig": "mock-valid-signature",
        "paypal-transmission-time": "2026-11-02T00:00:00Z",
    }
    body = {"id": "WH-1", "event_type": "PAYMENT.CAPTURE.COMPLETED"}

    monkeypatch.setattr(paypal_service_module, "PAYPAL_ALLOW_MOCK_WEBHOOKS", False)
    monkeypatch.setattr(paypal_service_module, "APP_ENV", "test")
    service.get_app_access_token = AsyncMock(side_effect=RuntimeError("no credentials"))
    assert await service.verify_webhook_signature(headers, body) is False
    service.get_app_access_token.assert_awaited_once()

    monkeypatch.setattr(paypal_service_module, "PAYPAL_ALLOW_MOCK_WEBHOOKS", True)
    assert await service.verify_webhook_signature(headers, body) is True

    monkeypatch.setattr(paypal_service_module, "APP_ENV", "production")
    service.get_app_access_token = AsyncMock(side_effect=RuntimeError("no credentials"))
    assert await service.verify_webhook_signature(headers, body) is False
    service.get_app_access_token.assert_awaited_once()


@pytest.mark.anyio
async def test_payout_http_failure_propagates_without_success_fallback(monkeypatch):
    service = PayPalService(
        client_id="sandbox-client",
        client_secret="sandbox-secret",
        base_url="https://api-m.sandbox.paypal.com",
    )
    service.get_access_token = AsyncMock(return_value={"access_token": "sandbox-token"})
    monkeypatch.setattr(paypal_service_module, "PAYPAL_PAYOUTS_ENABLED", True)
    payout_url = f"{service.base_url}/v1/payments/payouts"
    failure = httpx.Response(
        500,
        json={"name": "INTERNAL_SERVER_ERROR"},
        request=httpx.Request("POST", payout_url),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=failure):
        with pytest.raises(httpx.HTTPStatusError):
            await service.execute_payout(
                "child@example.com",
                15.0,
                "payout-test-id",
            )


@pytest.mark.anyio
async def test_payout_uses_sandbox_api_and_returns_paypal_batch(monkeypatch):
    service = PayPalService(
        client_id="sandbox-client",
        client_secret="sandbox-secret",
        base_url="https://api-m.sandbox.paypal.com",
    )
    service.get_access_token = AsyncMock(return_value={"access_token": "sandbox-token"})
    monkeypatch.setattr(paypal_service_module, "PAYPAL_PAYOUTS_ENABLED", True)
    payout_url = f"{service.base_url}/v1/payments/payouts"

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=_response(
            payout_url,
            {"batch_header": {"payout_batch_id": "BATCH-123", "batch_status": "PENDING"}},
        ),
    ) as post:
        result = await service.execute_payout(
            "child@example.com",
            15.0,
            "payout-test-id",
        )

    assert result["batch_id"] == "BATCH-123"
    assert result["status"] == "PENDING"
    assert post.call_args.kwargs["headers"]["PayPal-Request-Id"] == "payout-test-id"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer sandbox-token"
