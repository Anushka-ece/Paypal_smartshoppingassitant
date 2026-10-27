# Subagent Development Guide: AI-Powered PayPal Family Budgeting & Allowance Platform (`project_ver_1`)

This development guide outlines the architectural design, module breakdown, engineering specifications, and task instructions for subagents working on specific modules of the application. Each subagent should focus exclusively on their assigned module while adhering to the shared schema, conventions, and integration contracts defined below.

---

## 1. System Architecture & Tech Stack Reference

- **Backend API**: Python 3.11+ / FastAPI (`backend/app/`)
- **Database & Ledger**: PostgreSQL with TimescaleDB extension (Double-entry ledger design for audit integrity)
- **Cache & Async Tasks**: Redis & Celery (`backend/app/workers/celery_worker.py`)
- **AI / LLM Classifier & Policy Engine**: Google Generative AI (Gemini Flash) (`backend/app/services/gemini_service.py`)
- **Payment & Identity**: PayPal OAuth 2.0, Webhooks, Payouts API (`backend/app/services/paypal_service.py`)
- **Parent Web Dashboard**: Next.js 14 / React (`frontend/`)
- **Family Mobile Companion**: React Native / Expo (`mobile/`)

---

## 2. Module Breakdown & Subagent Task Assignments

### Module 1: Core Foundation, Database Schema & PayPal OAuth/Webhooks (Backend)
- **Target Files**: 
  - `backend/app/database.py`
  - `backend/app/api/auth.py`
  - `backend/app/api/webhooks.py`
  - `backend/app/models/` (User, Account, Transaction models)
- **Subagent Instructions**:
  1. Define SQLAlchemy models for `User` (Parent/Child roles), `Family`, `Account` (PayPal wallet mapping), and `Transaction` (Double-entry ledger with `debit`, `credit`, `status`, `refund_id`).
  2. Implement PayPal OAuth 2.0 token exchange and refresh endpoints in `backend/app/api/auth.py`.
  3. Implement PayPal Webhook verification middleware and endpoint handler in `backend/app/api/webhooks.py` supporting `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED`, and `CUSTOMER.DISPUTE.RESOLVED`. Note: In PayPal Sandbox, webhooks will be tested using PayPal Developer Dashboard webhook simulators and API mock triggers for transaction captures and refunds.
  4. Write robust unit tests in `backend/tests/` verifying webhook signature verification and ledger entry creation.

### Module 2: AI Tier-2 Classification & Natural Language Policy Guardrail Engine
- **Target Files**:
  - `backend/app/services/gemini_service.py`
  - `backend/app/api/transactions.py`
  - `backend/app/api/guardrails.py`
  - `backend/app/models/policy.py`
- **Subagent Instructions**:
  1. Implement Tier 1 fast-path normalizer (regex & hash map for common merchants like UBER, NETFLIX, STEAM) with latency <5ms.
  2. Implement Tier 2 Gemini Flash structured classifier returning category, subcategory, merchant clean name, confidence, and reasoning JSON schema.
  3. **LLM Fallback Strategy**: If Gemini API experiences latency >500ms or rate limiting after 3 retries, automatically fall back to the Tier 1 rule-based / keyword-matching classification engine and queue asynchronous background processing via Celery.
  4. Implement the Natural Language Policy Engine taking parent-defined plain-English rules (e.g., "Flag purchases over $25 on video games after 10 PM") and evaluating incoming transaction metadata.
  5. Integrate Redis caching for classification embeddings and rule evaluation results.

### Module 3: Allowances, Category Budgets & Refund Reconciliation Engine
- **Target Files**:
  - `backend/app/api/allowances.py`
  - `backend/app/services/paypal_service.py`
  - `backend/app/workers/celery_worker.py`
  - `backend/app/models/budget.py`
- **Subagent Instructions**:
  1. Implement category-wise envelope budgeting schema (allocating allowances to virtual envelopes like Free Spend, Books, Savings). Note: For version 1, all envelope calculations and allowances strictly normalize to USD base currency.
  2. Implement automated allowance scheduler via Celery and PayPal Payouts API (`POST /v1/payments/payouts`) with idempotency guards preventing double payouts.
  3. Implement the Refund Reconciliation Engine that listens to `PAYMENT.CAPTURE.REFUNDED` webhook events, locates the original debit entry, restores envelope balances, and marks transactions as `REFUNDED` without hard-deleting ledger entries.

### Module 4: Parent Web Dashboard (Next.js Frontend)
- **Target Files**:
  - `frontend/app/page.tsx`
  - `frontend/app/dashboard/`
  - `frontend/app/guardrails/`
  - `frontend/app/budgets/`
- **Subagent Instructions**:
  1. Build a modern, responsive Tailwind/React dashboard for parents.
  2. Implement views for Family Overview, Category Budget progress bars, Real-Time Flagged Transaction approvals (`[Approve]`, `[Review]`, `[Dispute/Freeze]`), and Natural Language Policy Editor.
  3. Connect frontend components to FastAPI backend endpoints via Axios/Fetch clients.

### Module 5: Family Mobile Companion App (React Native / Expo)
- **Target Files**:
  - `mobile/App.js`
  - `mobile/src/screens/`
  - `mobile/src/navigation/`
- **Subagent Instructions**:
  1. Create a cross-platform mobile companion app supporting dual roles (Parent view & Child view).
  2. For Child view: display personal allowance balance, envelope spend progress, transaction history, and "Purchase Request" submission form.
  3. For Parent view: push notification handlers (FCM/APNs) for instant transaction alerts with 1-tap authorization actions.

### Module 6: Security, Compliance, Testing & DevOps CI/CD
- **Target Files**:
  - `project_ver_1/.github/workflows/ci.yml`
  - `backend/tests/`
  - `backend/app/security/`
- **Subagent Instructions**:
  1. Implement end-to-end encryption for sensitive tokens and COPPA-compliant data handling for minor accounts. **COPPA Compliance**: Implement Verifiable Parental Consent (VPC) combining parent email verification and secure OAuth parental authorization/acknowledgment during onboarding to meet minimum FTC COPPA standards.
  2. Expand automated test suite covering webhook simulations, LLM schema validation, and refund reconciliation math.
  3. Finalize GitHub Actions CI workflow to run linters and pytest across pull requests.

---

## 3. Design Decisions & Resolution Summary

All open design clarifications have been resolved for version 1:
1. **PayPal Sandbox & Webhooks**: Handled via PayPal Developer Dashboard webhook simulators and API mock event triggers.
2. **LLM Fallback**: Automatic failover to Tier-1 rule/keyword matching after 3 retries on Gemini API latency (>500ms) or rate limit errors, with Celery async queueing.
3. **Multi-Currency Envelopes**: Version 1 strictly standardizes all family allowances and envelope budgets in USD.
4. **COPPA Compliance**: Minimum required FTC-compliant Verifiable Parental Consent (VPC) via parent email verification and secure OAuth parental authorization.
