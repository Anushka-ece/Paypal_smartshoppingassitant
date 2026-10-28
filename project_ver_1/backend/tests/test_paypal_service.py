from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.services import paypal_service


def test_payout_has_stable_idempotency_request_id(monkeypatch):
    monkeypatch.setattr(paypal_service, "PAYPAL_PAYOUTS_ENABLED", True)
    monkeypatch.setattr(paypal_service, "get_paypal_access_token", lambda: "sandbox-access")
    response = Mock(status_code=201)
    response.json.return_value = {"batch_header": {"payout_batch_id": "batch-id"}}
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(paypal_service.requests, "post", fake_post)
    paypal_service.execute_payout("child@example.test", "12.50", idempotency_key="allowance-4-20261027")
    url, kwargs = calls[0]
    assert url.endswith("/v1/payments/payouts")
    assert kwargs["json"]["sender_batch_header"]["sender_batch_id"] == "allowance-4-20261027"
    assert kwargs["json"]["items"][0]["amount"] == {"value": "12.50", "currency": "USD"}


def test_payout_rejects_non_usd_before_api_call(monkeypatch):
    monkeypatch.setattr(paypal_service, "PAYPAL_PAYOUTS_ENABLED", True)
    monkeypatch.setattr(paypal_service, "get_paypal_access_token", lambda: "token")
    with pytest.raises(HTTPException) as exc:
        paypal_service.execute_payout("child@example.test", 10, currency="EUR")
    assert exc.value.status_code == 422


def test_webhook_verification_requires_paypal_headers(monkeypatch):
    monkeypatch.setattr(paypal_service, "get_paypal_access_token", lambda: "token")
    assert paypal_service.verify_webhook_signature({}, {"id": "event"}, "webhook-id") is False
