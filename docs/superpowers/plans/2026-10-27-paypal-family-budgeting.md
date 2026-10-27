# PayPal Family Budgeting & Allowance Management Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI-powered family budgeting, allowance management, and transaction guardrail platform integrated with PayPal that provides real-time transaction categorization, plain-English parental spending rules, double-entry ledger audit integrity, automated refund reconciliation, and interactive incident workflows.

**Architecture:** A FastAPI backend backed by PostgreSQL with TimescaleDB hypertables for an immutable double-entry ledger, Redis/Celery for asynchronous tasks and scheduled allowances, and Google GenAI SDK (Gemini Flash) for two-tier transaction categorization and natural-language guardrail evaluation. The client layer comprises a Next.js 14 parent web dashboard and a React Native / Expo companion mobile application with push notification workflows.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL / TimescaleDB, Redis, Celery & Celery Beat, `google-genai` SDK, PayPal REST APIs (OAuth 2.0, Webhooks, Reporting, Payouts, Orders/Vault), Next.js 14 (App Router, Tailwind CSS), React Native / Expo, pytest.

**Spec:** [project_ver_1/DEVELOPMENT_GUIDE.md](file:///Users/nikhil/Desktop/Paypal_project/Paypal_smartshoppingassitant/project_ver_1/DEVELOPMENT_GUIDE.md) and [plan.txt](file:///Users/nikhil/Desktop/Paypal_project/Paypal_smartshoppingassitant/plan.txt)

---

## Global Constraints

- **Python Version**: Python 3.11+ strictly required.
- **Base Currency**: All envelope budgets, allowances, ledger entries, and transaction amounts must normalize to USD (`USD`).
- **Real-Time Webhook SLA**: End-to-end processing pipeline from `PAYMENT.CAPTURE.COMPLETED` webhook arrival to parent push notification must execute in <1.5 seconds.
- **Tier-1 Latency Target**: Instant cache and regex merchant normalizer must return in <5ms.
- **LLM Circuit Breaker**: If Gemini API latency exceeds 500ms or fails after 3 retries, fail over immediately to Tier-1 rule/keyword matching and queue background Celery refinement.
- **Ledger Immutability**: Strict double-entry ledger; no hard deletion of transactions or ledger records upon refund or dispute.
- **COPPA Compliance**: Verifiable Parental Consent (VPC) combining parent email verification and secure OAuth parental authorization required before onboarding minor accounts under 13.

---

## Review Focus

1. **Duplicate Webhook Delivery**: PayPal re-transmitting `PAYMENT.CAPTURE.COMPLETED` or refund webhooks must not create duplicate ledger debits or multiple refund credits. Pin with idempotency checks on `paypal_event_id` in Task 3.
2. **Partial Refunds**: A refund amount smaller than the original purchase (e.g., $15 refunded on a $50 purchase) must update status to `PARTIALLY_REFUNDED`, credit only the partial amount to the envelope, and retain the remaining debit. Pin in Task 7.
3. **Allowance Payout Cron Retry Bursts**: Celery worker restart or transient network failure during `POST /v1/payments/payouts` must use deterministic idempotency keys `(family_id, child_id, scheduled_date, allowance_id)` to guarantee zero duplicate payouts. Pin in Task 8.
4. **Gemini Latency Spike / Rate Limit during Webhook Processing**: If Gemini Flash takes >500ms or fails, fallback to Tier-1 rule classifier immediately so webhook response and push notification are not delayed past the 1.5s SLA. Pin in Task 5.
5. **Frozen Allowance During Child Dispute**: When a parent triggers `[Dispute / Freeze]` on a suspicious transaction, recurring allowance disbursements must immediately halt and remain blocked until the parent manually resolves the dispute. Pin in Task 8.

---

## File Structure

```
project_ver_1/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── allowances.py
│   │   │   ├── auth.py
│   │   │   ├── budgets.py
│   │   │   ├── family.py
│   │   │   ├── guardrails.py
│   │   │   ├── purchase_requests.py
│   │   │   ├── transactions.py
│   │   │   └── webhooks.py
│   │   ├── models/
│   │   │   ├── account.py
│   │   │   ├── budget.py
│   │   │   ├── family.py
│   │   │   ├── invite.py
│   │   │   ├── ledger.py
│   │   │   ├── policy.py
│   │   │   ├── purchase_request.py
│   │   │   ├── transaction.py
│   │   │   └── user.py
│   │   ├── security/
│   │   │   ├── coppa.py
│   │   │   └── crypto.py
│   │   ├── services/
│   │   │   ├── embedding_service.py
│   │   │   ├── gemini_service.py
│   │   │   ├── paypal_service.py
│   │   │   └── reputation_service.py
│   │   ├── workers/
│   │   │   ├── celery_schedule.py
│   │   │   └── celery_worker.py
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   └── tests/
│       ├── test_allowances.py
│       ├── test_auth.py
│       ├── test_classification.py
│       ├── test_guardrails.py
│       ├── test_history_sync.py
│       ├── test_ledger.py
│       ├── test_purchase_requests.py
│       ├── test_reconciliation.py
│       └── test_webhooks.py
├── frontend/
│   ├── app/
│   │   ├── budgets/page.tsx
│   │   ├── dashboard/page.tsx
│   │   ├── family/page.tsx
│   │   ├── guardrails/
│   │   │   ├── page.tsx
│   │   │   └── simulator/page.tsx
│   │   ├── requests/page.tsx
│   │   └── page.tsx
│   └── package.json
└── mobile/
    ├── src/
    │   ├── navigation/AppNavigator.js
    │   ├── screens/
    │   │   ├── EnvelopesScreen.js
    │   │   ├── HomeScreen.js
    │   │   ├── ParentAlertModal.js
    │   │   ├── PurchaseRequestScreen.js
    │   │   └── ReviewActionScreen.js
    │   └── services/notifications.js
    ├── App.js
    └── package.json
```

---

## Tasks

### Task 1: Core Database Engine & TimescaleDB Double-Entry Ledger Models

**Files:**
- Modify: `project_ver_1/backend/app/database.py`
- Create: `project_ver_1/backend/app/models/user.py`
- Create: `project_ver_1/backend/app/models/family.py`
- Create: `project_ver_1/backend/app/models/invite.py`
- Create: `project_ver_1/backend/app/models/account.py`
- Create: `project_ver_1/backend/app/models/transaction.py`
- Create: `project_ver_1/backend/app/models/ledger.py`
- Test: `project_ver_1/backend/tests/test_ledger.py`

**Interfaces:**
- Consumes: PostgreSQL connection string from `backend/app/config.py`.
- Produces: SQLAlchemy session dependency `get_db()`, models `User`, `Family`, `FamilyInvite`, `Account`, `Transaction`, and `LedgerEntry`.

- [ ] **Step 1: Write the failing test for ledger double-entry debit/credit balance constraint**

```python
# project_ver_1/backend/tests/test_ledger.py
import pytest
from app.models.ledger import LedgerEntry

def test_ledger_double_entry_balance():
    entry = LedgerEntry(
        debit_account_id=1,
        credit_account_id=2,
        amount=25.00,
        currency="USD",
        status="COMPLETED"
    )
    assert entry.debit_account_id != entry.credit_account_id
    assert entry.amount > 0
    assert entry.currency == "USD"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest project_ver_1/backend/tests/test_ledger.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.ledger'`

- [ ] **Step 3: Implement database engine, TimescaleDB hypertable setup, and models**

In `backend/app/database.py`, initialize declarative base, `get_db` generator, and a function `init_timescaledb()` executing `SELECT create_hypertable('ledger_entries', 'created_at', if_not_exists => TRUE);`.  
In `backend/app/models/`, create `User` (roles: `PARENT`, `CO_PARENT`, `CHILD`), `Family`, `FamilyInvite`, `Account` (`account_type`: `PARENT_WALLET`, `CHILD_VIRTUAL`, `PAYPAL_LINKED`), `Transaction` (`status`: `COMPLETED`, `FLAGGED`, `REFUNDED`, `PARTIALLY_REFUNDED`, `DISPUTED`), and `LedgerEntry` (`debit_account_id`, `credit_account_id`, `amount`, `currency`, `created_at`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest project_ver_1/backend/tests/test_ledger.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add project_ver_1/backend/app/database.py project_ver_1/backend/app/models/ project_ver_1/backend/tests/test_ledger.py
git commit -m "feat(backend): implement TimescaleDB double-entry ledger models"
```

---

### Task 2: PayPal Identity, OAuth 2.0 & Token Encryption Lifecycle

**Files:**
- Create: `project_ver_1/backend/app/security/crypto.py`
- Modify: `project_ver_1/backend/app/services/paypal_service.py`
- Modify: `project_ver_1/backend/app/api/auth.py`
- Test: `project_ver_1/backend/tests/test_auth.py`

**Interfaces:**
- Consumes: PayPal Client ID and Secret from `config.py`.
- Produces: `encrypt_token(raw: str) -> str`, `decrypt_token(cipher: str) -> str`, `PayPalService.exchange_oauth_code(code: str) -> dict`, `PayPalService.refresh_token(refresh_token: str) -> dict`, endpoints `/api/auth/paypal/authorize` and `/api/auth/paypal/callback`.

- [ ] **Step 1: Write the failing test for token encryption and OAuth exchange**

```python
# project_ver_1/backend/tests/test_auth.py
from app.security.crypto import encrypt_token, decrypt_token

def test_token_encryption_roundtrip():
    token = "secret-paypal-oauth-refresh-token"
    encrypted = encrypt_token(token)
    assert encrypted != token
    assert decrypt_token(encrypted) == token
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest project_ver_1/backend/tests/test_auth.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.security.crypto'`

- [ ] **Step 3: Implement AES-256 token encryption and PayPal OAuth exchange**

Implement `encrypt_token` and `decrypt_token` using `cryptography.fernet.Fernet` or AES-GCM in `backend/app/security/crypto.py`.  
In `backend/app/services/paypal_service.py`, implement `exchange_oauth_code(code)` and `refresh_access_token(encrypted_refresh_token)` using `httpx.AsyncClient` against PayPal OAuth 2.0 endpoint (`https://api-m.sandbox.paypal.com/v1/oauth2/token`).  
In `backend/app/api/auth.py`, expose `/authorize` generating the PayPal OAuth redirect URL and `/callback` storing encrypted tokens for the user account.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest project_ver_1/backend/tests/test_auth.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add project_ver_1/backend/app/security/crypto.py project_ver_1/backend/app/services/paypal_service.py project_ver_1/backend/app/api/auth.py project_ver_1/backend/tests/test_auth.py
git commit -m "feat(auth): implement PayPal OAuth 2.0 exchange and token encryption"
```

---

### Task 3: PayPal Webhook Verification & Routing Engine

**Files:**
- Modify: `project_ver_1/backend/app/services/paypal_service.py`
- Modify: `project_ver_1/backend/app/api/webhooks.py`
- Test: `project_ver_1/backend/tests/test_webhooks.py`

**Interfaces:**
- Consumes: PayPal webhook headers (`PAYPAL-AUTH-ALGO`, `PAYPAL-CERT-URL`, `PAYPAL-TRANSMISSION-ID`, `PAYPAL-TRANSMISSION-SIG`, `PAYPAL-TRANSMISSION-TIME`) and webhook ID.
- Produces: `verify_webhook_signature(headers: dict, body: bytes) -> bool`, endpoint `POST /api/webhooks/paypal`.

- [ ] **Step 1: Write the failing test for webhook signature verification and idempotency**

```python
# project_ver_1/backend/tests/test_webhooks.py
from app.services.paypal_service import PayPalService

def test_webhook_event_filtering():
    service = PayPalService()
    supported = ["PAYMENT.CAPTURE.COMPLETED", "PAYMENT.CAPTURE.REFUNDED", "PAYMENT.SALE.REFUNDED", "CUSTOMER.DISPUTE.RESOLVED"]
    for event_type in supported:
        assert service.is_event_supported(event_type) is True
    assert service.is_event_supported("UNKNOWN.EVENT") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest project_ver_1/backend/tests/test_webhooks.py -v`  
Expected: FAIL with `AttributeError: 'PayPalService' object has no attribute 'is_event_supported'`

- [ ] **Step 3: Implement webhook signature verification and event router**

In `backend/app/services/paypal_service.py`, implement `verify_webhook_signature` calling PayPal's `/v1/notifications/verify-webhook-signature` API endpoint and `is_event_supported`.  
In `backend/app/api/webhooks.py`, verify headers, parse event, check `paypal_event_id` deduplication in Redis/PostgreSQL to prevent duplicate processing, and route:
  - `PAYMENT.CAPTURE.COMPLETED` $\rightarrow$ Module 2 evaluation pipeline.
  - `PAYMENT.CAPTURE.REFUNDED` & `PAYMENT.SALE.REFUNDED` $\rightarrow$ Module 3 reconciliation pipeline.
  - `CUSTOMER.DISPUTE.RESOLVED` $\rightarrow$ Dispute resolution handler.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest project_ver_1/backend/tests/test_webhooks.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add project_ver_1/backend/app/services/paypal_service.py project_ver_1/backend/app/api/webhooks.py project_ver_1/backend/tests/test_webhooks.py
git commit -m "feat(webhooks): implement PayPal webhook verification and routing engine"
```

---

### Task 4: Historical Transaction Ingestion via PayPal Reporting API

**Files:**
- Modify: `project_ver_1/backend/app/services/paypal_service.py`
- Modify: `project_ver_1/backend/app/workers/celery_worker.py`
- Test: `project_ver_1/backend/tests/test_history_sync.py`

**Interfaces:**
- Consumes: Account PayPal access token.
- Produces: `fetch_historical_transactions(access_token: str, start_date: str, end_date: str) -> list[dict]`, Celery task `sync_historical_transactions_task(account_id: int)`.

- [ ] **Step 1: Write the failing test for historical transaction extraction**

```python
# project_ver_1/backend/tests/test_history_sync.py
from app.services.paypal_service import PayPalService

def test_parse_transaction_search_record():
    service = PayPalService()
    raw_record = {
        "transaction_info": {
            "transaction_id": "TX123",
            "transaction_amount": {"value": "45.00", "currency_code": "USD"},
            "transaction_status": "S",
            "transaction_initiation_date": "2026-10-01T12:00:00Z"
        },
        "payer_info": {"payer_name": {"alternate_full_name": "Steam Games"}}
    }
    parsed = service.parse_transaction_record(raw_record)
    assert parsed["transaction_id"] == "TX123"
    assert parsed["amount"] == 45.00
    assert parsed["currency"] == "USD"
    assert parsed["merchant_name"] == "Steam Games"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest project_ver_1/backend/tests/test_history_sync.py -v`  
Expected: FAIL with `AttributeError: 'PayPalService' object has no attribute 'parse_transaction_record'`

- [ ] **Step 3: Implement Transaction Search API client and background sync task**

In `backend/app/services/paypal_service.py`, implement `fetch_historical_transactions` calling `/v1/reporting/transactions` for 30–90 days of history and `parse_transaction_record`.  
In `backend/app/workers/celery_worker.py`, implement `sync_historical_transactions_task` which ingests historical records, writes ledger entries, and queues them for categorization.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest project_ver_1/backend/tests/test_history_sync.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add project_ver_1/backend/app/services/paypal_service.py project_ver_1/backend/app/workers/celery_worker.py project_ver_1/backend/tests/test_history_sync.py
git commit -m "feat(reporting): implement historical transaction ingestion via PayPal Reporting API"
```

---

### Task 5: Two-Tier Expense Categorization & Reclassification Learning Loop

**Files:**
- Create: `project_ver_1/backend/app/services/embedding_service.py`
- Modify: `project_ver_1/backend/app/services/gemini_service.py`
- Modify: `project_ver_1/backend/app/api/transactions.py`
- Test: `project_ver_1/backend/tests/test_classification.py`

**Interfaces:**
- Consumes: `merchant_name`, `description`, `amount`.
- Produces: `Tier1Classifier.classify(...) -> dict | None`, `classify_transaction(merchant_name: str, description: str, amount: float) -> dict`, endpoint `POST /api/transactions/{id}/reclassify`.

- [ ] **Step 1: Write the failing test for Tier-1 normalizer and Gemini structured schema**

```python
# project_ver_1/backend/tests/test_classification.py
from app.services.embedding_service import Tier1Classifier

def test_tier1_fast_path_match():
    classifier = Tier1Classifier()
    res = classifier.classify("UBER *TRIP 1234", 18.50)
    assert res is not None
    assert res["category"] == "Transport"
    assert res["merchant_clean_name"] == "Uber"
    assert res["confidence"] >= 0.95
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest project_ver_1/backend/tests/test_classification.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.embedding_service'`

- [ ] **Step 3: Implement Tier-1 normalizer, Tier-2 Gemini Flash classifier, and reclassification loop**

In `backend/app/services/embedding_service.py`, build regex and hash dictionary mapping known merchants (Uber, Netflix, Steam, Spotify, Amazon) to categories (<5ms latency).  
In `backend/app/services/gemini_service.py`, use the Google GenAI SDK (`google.genai`) with Gemini Flash and structured response schema (`category`, `subcategory`, `merchant_clean_name`, `confidence`, `tags`, `reasoning`). Implement a 500ms timeout circuit breaker falling back to Tier 1.  
In `backend/app/api/transactions.py`, expose `POST /{id}/reclassify` taking parent category corrections, saving to database, and storing custom family overrides in Redis.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest project_ver_1/backend/tests/test_classification.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add project_ver_1/backend/app/services/embedding_service.py project_ver_1/backend/app/services/gemini_service.py project_ver_1/backend/app/api/transactions.py project_ver_1/backend/tests/test_classification.py
git commit -m "feat(ai): implement two-tier expense categorization and parental learning loop"
```

---

### Task 6: Merchant Threat Database & Natural Language Policy Guardrail Engine

**Files:**
- Create: `project_ver_1/backend/app/services/reputation_service.py`
- Create: `project_ver_1/backend/app/models/policy.py`
- Modify: `project_ver_1/backend/app/services/gemini_service.py`
- Modify: `project_ver_1/backend/app/api/guardrails.py`
- Test: `project_ver_1/backend/tests/test_guardrails.py`

**Interfaces:**
- Consumes: Transaction metadata and list of parent natural-language rules.
- Produces: `ReputationService.check_merchant(merchant_name: str) -> dict`, `evaluate_policy(rules: list[str], transaction: dict) -> dict`, endpoints `POST /api/guardrails` and `POST /api/guardrails/simulate`.

- [ ] **Step 1: Write the failing test for threat blacklist and policy evaluation schema**

```python
# project_ver_1/backend/tests/test_guardrails.py
from app.services.reputation_service import ReputationService

def test_reputation_blacklist_detection():
    service = ReputationService()
    result = service.check_merchant("crypto-instant-payout.biz")
    assert result["is_high_risk"] is True
    assert "crypto" in result["matched_category"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest project_ver_1/backend/tests/test_guardrails.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.reputation_service'`

- [ ] **Step 3: Implement reputation blacklist and LLM natural-language policy evaluator**

In `backend/app/services/reputation_service.py`, build high-risk merchant blacklist for gambling, crypto on-ramps, unverified game key sites, and predatory microtransactions.  
In `backend/app/services/gemini_service.py`, implement `evaluate_policy` prompting Gemini Flash with active parental rules and transaction details, returning strict JSON: `is_flagged`, `risk_level`, `matched_rules`, `summary_for_parent`, `requires_immediate_action`.  
In `backend/app/api/guardrails.py`, provide policy CRUD and `POST /simulate` to test draft rules against sample transactions.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest project_ver_1/backend/tests/test_guardrails.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add project_ver_1/backend/app/services/reputation_service.py project_ver_1/backend/app/models/policy.py project_ver_1/backend/app/services/gemini_service.py project_ver_1/backend/app/api/guardrails.py project_ver_1/backend/tests/test_guardrails.py
git commit -m "feat(guardrails): implement threat blacklist and natural language policy evaluator"
```

---

### Task 7: Virtual Envelope Budgeting & Automated Refund Reconciliation Engine

**Files:**
- Create: `project_ver_1/backend/app/models/budget.py`
- Modify: `project_ver_1/backend/app/api/budgets.py`
- Modify: `project_ver_1/backend/app/api/webhooks.py`
- Test: `project_ver_1/backend/tests/test_reconciliation.py`

**Interfaces:**
- Consumes: Refund webhook payloads (`PAYMENT.CAPTURE.REFUNDED`, `PAYMENT.SALE.REFUNDED`).
- Produces: `reconcile_refund(refund_payload: dict, db: Session) -> dict`, endpoints `/api/budgets/envelopes`.

- [ ] **Step 1: Write the failing test for net-zero refund reconciliation math**

```python
# project_ver_1/backend/tests/test_reconciliation.py
from app.api.budgets import apply_refund_to_envelope

def test_full_refund_envelope_balance_restoration():
    envelope = {"name": "Gaming", "allocated": 50.00, "spent": 40.00}
    updated = apply_refund_to_envelope(envelope, refund_amount=40.00)
    assert updated["spent"] == 0.00
    assert updated["remaining"] == 50.00

def test_partial_refund_envelope_balance():
    envelope = {"name": "Gaming", "allocated": 50.00, "spent": 40.00}
    updated = apply_refund_to_envelope(envelope, refund_amount=15.00)
    assert updated["spent"] == 25.00
    assert updated["remaining"] == 25.00
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest project_ver_1/backend/tests/test_reconciliation.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.budgets'` or `ImportError`

- [ ] **Step 3: Implement envelope budgeting and refund reconciliation logic**

In `backend/app/models/budget.py`, define `BudgetEnvelope` (fields: `family_id`, `name`, `allocated_amount`, `current_spent`, `currency="USD"`).  
In `backend/app/api/budgets.py`, implement `apply_refund_to_envelope` and envelope CRUD.  
In `backend/app/api/webhooks.py`, link `PAYMENT.CAPTURE.REFUNDED` and `PAYMENT.SALE.REFUNDED` to find the original debit by `parent_payment_id`, restore the envelope `spent` amount, and update transaction status to `REFUNDED` (or `PARTIALLY_REFUNDED` if refund < original) without deleting records.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest project_ver_1/backend/tests/test_reconciliation.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add project_ver_1/backend/app/models/budget.py project_ver_1/backend/app/api/budgets.py project_ver_1/backend/app/api/webhooks.py project_ver_1/backend/tests/test_reconciliation.py
git commit -m "feat(budget): implement virtual envelope budgeting and refund reconciliation"
```

---

### Task 8: Automated Allowance Engine with Idempotent Payouts & Incident Freeze

**Files:**
- Create: `project_ver_1/backend/app/workers/celery_schedule.py`
- Modify: `project_ver_1/backend/app/services/paypal_service.py`
- Modify: `project_ver_1/backend/app/api/allowances.py`
- Test: `project_ver_1/backend/tests/test_allowances.py`

**Interfaces:**
- Consumes: Family allowance schedule configuration.
- Produces: `generate_idempotency_key(family_id: int, child_id: int, date: str, allowance_id: int) -> str`, `disburse_allowance(allowance_id: int)`, endpoints `/api/allowances`, `/api/allowances/{id}/freeze`, `/api/allowances/{id}/unfreeze`.

- [ ] **Step 1: Write the failing test for allowance idempotency and freeze logic**

```python
# project_ver_1/backend/tests/test_allowances.py
from app.api.allowances import generate_payout_idempotency_key, should_execute_allowance

def test_idempotency_key_deterministic():
    key1 = generate_payout_idempotency_key(family_id=10, child_id=5, date="2026-11-01", allowance_id=1)
    key2 = generate_payout_idempotency_key(family_id=10, child_id=5, date="2026-11-01", allowance_id=1)
    assert key1 == key2

def test_frozen_allowance_blocks_disbursement():
    schedule = {"allowance_id": 1, "is_frozen": True, "amount": 20.00}
    assert should_execute_allowance(schedule) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest project_ver_1/backend/tests/test_allowances.py -v`  
Expected: FAIL with `ImportError: cannot import name 'generate_payout_idempotency_key'`

- [ ] **Step 3: Implement Celery Beat scheduler, PayPal Payouts integration, and freeze states**

In `backend/app/services/paypal_service.py`, implement `execute_payout(receiver_email: str, amount: float, idempotency_key: str)` targeting PayPal's `POST /v1/payments/payouts`.  
In `backend/app/api/allowances.py`, implement schedule management and freeze/unfreeze endpoints.  
In `backend/app/workers/celery_schedule.py`, register periodic tasks running weekly, bi-weekly, or monthly on the 1st, checking `is_frozen == False` before disbursement.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest project_ver_1/backend/tests/test_allowances.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add project_ver_1/backend/app/workers/celery_schedule.py project_ver_1/backend/app/services/paypal_service.py project_ver_1/backend/app/api/allowances.py project_ver_1/backend/tests/test_allowances.py
git commit -m "feat(allowances): implement idempotent PayPal payouts scheduler and incident freeze"
```

---

### Task 9: Pre-Purchase Request Mode & PayPal Vault / Orders Flow

**Files:**
- Create: `project_ver_1/backend/app/models/purchase_request.py`
- Create: `project_ver_1/backend/app/api/purchase_requests.py`
- Modify: `project_ver_1/backend/app/services/paypal_service.py`
- Test: `project_ver_1/backend/tests/test_purchase_requests.py`

**Interfaces:**
- Consumes: Child item URL, item name, amount.
- Produces: `PurchaseRequest` model, endpoints `POST /api/purchase-requests` and `POST /api/purchase-requests/{id}/approve`.

- [ ] **Step 1: Write the failing test for purchase request creation and approval states**

```python
# project_ver_1/backend/tests/test_purchase_requests.py
from app.models.purchase_request import PurchaseRequest

def test_purchase_request_initial_state():
    req = PurchaseRequest(
        child_id=2,
        item_name="Roblox Digital Code",
        store_url="https://store.example.com",
        amount=15.00,
        currency="USD",
        status="PENDING_APPROVAL"
    )
    assert req.status == "PENDING_APPROVAL"
    assert req.amount == 15.00
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest project_ver_1/backend/tests/test_purchase_requests.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.purchase_request'`

- [ ] **Step 3: Implement Pre-Purchase Request models and execution endpoints**

In `backend/app/models/purchase_request.py`, define `PurchaseRequest` (`status`: `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `EXECUTED`).  
In `backend/app/api/purchase_requests.py`, implement creation endpoint (evaluating the link via Gemini policy guardrails) and approval endpoint (invoking PayPal Vault token payment or Payouts).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest project_ver_1/backend/tests/test_purchase_requests.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add project_ver_1/backend/app/models/purchase_request.py project_ver_1/backend/app/api/purchase_requests.py project_ver_1/backend/app/services/paypal_service.py project_ver_1/backend/tests/test_purchase_requests.py
git commit -m "feat(requests): implement Pre-Purchase Request mode and store approval pipeline"
```

---

### Task 10: Parent Web Dashboard (Next.js Frontend)

**Files:**
- Modify: `project_ver_1/frontend/app/page.tsx`
- Create: `project_ver_1/frontend/app/dashboard/page.tsx`
- Create: `project_ver_1/frontend/app/budgets/page.tsx`
- Create: `project_ver_1/frontend/app/guardrails/page.tsx`
- Create: `project_ver_1/frontend/app/guardrails/simulator/page.tsx`
- Create: `project_ver_1/frontend/app/requests/page.tsx`
- Create: `project_ver_1/frontend/app/family/page.tsx`

**Interfaces:**
- Consumes: Backend REST endpoints (`/api/transactions`, `/api/budgets`, `/api/guardrails`, `/api/purchase-requests`, `/api/family`).
- Produces: Responsive web application for parents.

- [ ] **Step 1: Build the responsive Next.js Parent Dashboard layouts**

In `frontend/app/dashboard/page.tsx`, implement overview cards for total family spend, balance envelopes, and flagged transaction alert cards with 1-click action triggers:
  - `[Approve]`
  - `[Flag for Review]` (demands receipt upload / kid explanation)
  - `[Dispute / Freeze]` (freezes upcoming payouts and provides direct link to PayPal Resolution Center: `https://www.paypal.com/disputes/`)

- [ ] **Step 2: Implement Envelope Budgets page with "Hide refunded transactions" toggle**

In `frontend/app/budgets/page.tsx`, display category spend vs limit progress bars and a ledger table equipped with a client-side filter toggle for **"Hide refunded transactions"**.

- [ ] **Step 3: Implement Natural Language Policy Editor & Simulator**

In `frontend/app/guardrails/page.tsx`, create policy management.  
In `frontend/app/guardrails/simulator/page.tsx`, create an interactive sandbox where parents can draft a plain-English rule, run it against test transactions, and inspect the resulting JSON risk analysis in real time.

- [ ] **Step 4: Implement Pre-Purchase Request & Family Member pages**

In `frontend/app/requests/page.tsx`, display pending child store requests with item links and approve/deny actions.  
In `frontend/app/family/page.tsx`, generate invite links for co-parents and teens.

- [ ] **Step 5: Verify frontend builds without errors**

Run: `cd project_ver_1/frontend && npm run build` (or `npm test`)  
Expected: PASS with 0 build errors.

- [ ] **Step 6: Commit**

```bash
git add project_ver_1/frontend/app/
git commit -m "feat(frontend): implement Next.js parent web dashboard, budget progress bars, and rule simulator"
```

---

### Task 11: Family Mobile Companion App (React Native / Expo)

**Files:**
- Modify: `project_ver_1/mobile/App.js`
- Create: `project_ver_1/mobile/src/navigation/AppNavigator.js`
- Create: `project_ver_1/mobile/src/screens/HomeScreen.js`
- Create: `project_ver_1/mobile/src/screens/EnvelopesScreen.js`
- Create: `project_ver_1/mobile/src/screens/PurchaseRequestScreen.js`
- Create: `project_ver_1/mobile/src/screens/ReviewActionScreen.js`
- Create: `project_ver_1/mobile/src/screens/ParentAlertModal.js`
- Create: `project_ver_1/mobile/src/services/notifications.js`

**Interfaces:**
- Consumes: Backend API endpoints and FCM/APNs push notifications.
- Produces: Dual-role mobile application for Parents and Children.

- [ ] **Step 1: Configure Dual-Role Navigation and Home Screens**

In `mobile/src/navigation/AppNavigator.js`, provide role-based navigation branches for Child and Parent.  
In `mobile/src/screens/HomeScreen.js`, display personal balance and recent transactions.

- [ ] **Step 2: Implement Child Purchase Request & Review Action Screens**

In `mobile/src/screens/PurchaseRequestScreen.js`, build form for item URL, merchant, and dollar amount.  
In `mobile/src/screens/ReviewActionScreen.js`, provide receipt photo upload and explanation textbox for transactions marked `[Flag for Review]`.

- [ ] **Step 3: Implement Parent Instant Alert Modal & Push Notifications**

In `mobile/src/services/notifications.js`, register FCM/APNs push handlers.  
In `mobile/src/screens/ParentAlertModal.js`, present high-priority alert cards with 1-tap `Approve`, `Request Review`, or `Freeze/Dispute` actions within 1.5 seconds of purchase.

- [ ] **Step 4: Commit**

```bash
git add project_ver_1/mobile/
git commit -m "feat(mobile): implement React Native family companion app and real-time push alerts"
```

---

### Task 12: Security Hardening, COPPA Compliance & CI/CD Pipeline

**Files:**
- Create: `project_ver_1/backend/app/security/coppa.py`
- Modify: `project_ver_1/.github/workflows/ci.yml`
- Test: `project_ver_1/backend/tests/`

**Interfaces:**
- Consumes: Minor birth dates, parent email, parent PayPal OAuth session.
- Produces: `verify_parental_consent(parent_user_id: int, child_birthdate: date) -> bool`, automated CI/CD pipeline.

- [ ] **Step 1: Write the failing test for COPPA Verifiable Parental Consent**

```python
# project_ver_1/backend/tests/test_coppa.py
from datetime import date
from app.security.coppa import is_coppa_minor, verify_parental_consent

def test_coppa_age_check():
    assert is_coppa_minor(date(2018, 1, 1)) is True
    assert is_coppa_minor(date(2005, 1, 1)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest project_ver_1/backend/tests/test_coppa.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.security.coppa'`

- [ ] **Step 3: Implement COPPA VPC verification and GitHub Actions CI workflow**

In `backend/app/security/coppa.py`, enforce FTC-compliant Verifiable Parental Consent: requiring verified parent email and active authenticated PayPal OAuth session before provisioning accounts for minors under 13.  
In `.github/workflows/ci.yml`, set up matrix testing across Python 3.11+, Node 18+, running flake8/black, pytest, and frontend builds.

- [ ] **Step 4: Run all test suites across the repository**

Run: `pytest project_ver_1/backend/tests/ -v`  
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add project_ver_1/backend/app/security/coppa.py project_ver_1/.github/workflows/ci.yml project_ver_1/backend/tests/test_coppa.py
git commit -m "feat(security): implement COPPA verifiable parental consent and CI workflow"
```

---

## Execution Handoff

Plan complete and saved to [docs/superpowers/plans/2026-10-27-paypal-family-budgeting.md](file:///Users/nikhil/Desktop/Paypal_project/Paypal_smartshoppingassitant/docs/superpowers/plans/2026-10-27-paypal-family-budgeting.md). Please review the plan. Which execution approach would you prefer?

- **Subagent-driven** - A fresh subagent implements each task and a fresh reviewer checks it before the next one starts, then a whole-branch review at the end. Most thorough; costs a fresh context per task and per review.
- **Native** - I implement every task myself in this session, the way this harness runs work, then one fresh reviewer on the most capable model checks the whole branch. Cheapest and fastest; no independent review until the end. Runs well with a mid-tier session model, since the plan carries the design.

**For this plan I recommend Subagent-driven**, because the 12 tasks span independent architectural tiers (TimescaleDB ledger, PayPal OAuth/webhooks, Gemini Flash classification, Celery schedulers, Next.js dashboard, and React Native mobile) whose interface contracts are explicitly locked in and will benefit from fresh review gates at each boundary. Does the plan capture what you want, and which approach should we use?

