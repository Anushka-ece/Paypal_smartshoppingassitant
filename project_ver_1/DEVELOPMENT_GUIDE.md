# Subagent Development Guide: AI-Powered PayPal Family Budgeting & Allowance Platform (`project_ver_1`)

This development guide outlines the architectural design, module breakdown, engineering specifications, and task instructions for subagents working on specific modules of the application. Each subagent should focus exclusively on their assigned module while adhering to the shared schema, conventions, and integration contracts defined below.

---

## 1. System Architecture & Tech Stack Reference

- **Backend API**: Python 3.11+ / FastAPI (`backend/app/`)
- **Database & Ledger**: PostgreSQL with TimescaleDB extension (Double-entry ledger design for audit integrity; hypertables on transaction timestamp)
- **Cache, Task Queue & Cron**: Redis & Celery / Celery Beat (`backend/app/workers/celery_worker.py`, `backend/app/workers/celery_schedule.py`)
- **AI / LLM Classifier & Policy Engine**: Google GenAI SDK (Gemini 2.5 Flash / Gemini 3.8 Flash) (`backend/app/services/gemini_service.py`)
- **Payment & Identity APIs**:
  - PayPal OAuth 2.0 (Identity API)
  - PayPal Webhooks API (Captures, Sales, Refunds, Disputes)
  - PayPal Transaction Search API (`/v1/reporting/transactions` for historical sync)
  - PayPal Payouts API (`POST /v1/payments/payouts` with idempotency)
  - PayPal Orders & Vault API (pre-approved payment tokens for Pre-Purchase Request Mode)
- **Parent Web Dashboard**: Next.js 14 / React / Tailwind CSS (`frontend/`)
- **Family Mobile Companion**: React Native / Expo (`mobile/`)
- **Push Notification Service**: Firebase Cloud Messaging (FCM) & Apple APNs

---

## 2. Module Breakdown & Subagent Task Assignments

### Module 1: Core Foundation, TimescaleDB Ledger, Family Hierarchy & PayPal Integration (Backend)
- **Target Files**:
  - `backend/app/database.py` (SQLAlchemy connection & TimescaleDB hypertable setup)
  - `backend/app/api/auth.py` (OAuth login, token exchange, refresh lifecycle)
  - `backend/app/api/webhooks.py` (PayPal Webhook verification & routing)
  - `backend/app/api/family.py` (Family creation, invite links/tokens for co-parents and teens)
  - `backend/app/models/` (`user.py`, `family.py`, `invite.py`, `account.py`, `transaction.py`, `ledger.py`)
  - `backend/app/services/paypal_service.py` (OAuth, Webhooks, Reporting API)
- **Subagent Instructions**:
  1. **Data Models & Double-Entry Ledger**:
     - Define SQLAlchemy models for `User` (Parent, Co-parent, Child roles), `Family`, `FamilyInvite`, `Account` (PayPal wallet mapping, Venmo Teen, or sub-login), and `Transaction` / `LedgerEntry`.
     - Ledger entries must follow strict double-entry accounting (`debit_account_id`, `credit_account_id`, `amount`, `status`: `COMPLETED`, `FLAGGED`, `REFUNDED`, `PARTIALLY_REFUNDED`, `DISPUTED`, `refund_id`).
  2. **TimescaleDB Integration**: Configure hypertable on `ledger_entries` partitioned on `created_at` for high-throughput financial time-series audit queries.
  3. **PayPal OAuth 2.0 & Token Lifecycle**: Implement token exchange, automatic token refresh, and encrypted token storage in `backend/app/api/auth.py`.
  4. **Historical Transaction Sync**:
     - Implement PayPal Transaction Search API client (`GET /v1/reporting/transactions`).
     - Trigger an asynchronous Celery task on account link to backfill the last 30–90 days of transactions into the ledger and queue them for Tier-1/Tier-2 categorization.
  5. **PayPal Webhooks Engine**:
     - Implement webhook verification middleware validating PayPal cryptographic signatures (`PAYPAL-AUTH-ALGO`, `PAYPAL-CERT-URL`, `PAYPAL-TRANSMISSION-ID`, `PAYPAL-TRANSMISSION-SIG`, `PAYPAL-TRANSMISSION-TIME`).
     - Support events: `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED`, `PAYMENT.SALE.REFUNDED`, and `CUSTOMER.DISPUTE.RESOLVED`.
     - Dispatch `PAYMENT.CAPTURE.COMPLETED` events to the Module 2 evaluation pipeline within a target end-to-end SLA of <1.5s.
  6. **Family Onboarding & RBAC**: Implement family invitation endpoints generating secure, expiring invite tokens for co-parents and children.
  7. **Testing**: Write unit tests in `backend/tests/test_webhooks.py` and `backend/tests/test_auth.py` covering token exchange, valid/invalid cryptographic webhook signatures, and ledger debit/credit balance equality.

---

### Module 2: AI Classification, Threat Evaluation & Natural Language Policy Guardrail Engine
- **Target Files**:
  - `backend/app/services/gemini_service.py` (Google GenAI SDK structured classification & policy evaluation)
  - `backend/app/services/reputation_service.py` (Known scam database & high-risk merchant blacklist)
  - `backend/app/services/embedding_service.py` (Tier 1 vector/hash lookups & family-specific customization)
  - `backend/app/api/transactions.py` (Transaction listing, reclassification endpoint)
  - `backend/app/api/guardrails.py` (Natural language policy CRUD & interactive test simulator)
  - `backend/app/models/policy.py`
- **Subagent Instructions**:
  1. **Two-Tier Categorization Pipeline**:
     - **Tier 1 (Instant Cache & Rules Engine)**: Fast regex normalization and hash map / embedding lookup for standard merchants (e.g., UBER *TRIP -> Transport, NETFLIX.COM -> Entertainment) with latency <5ms.
     - **Tier 2 (Gemini Flash Classifier)**: For unknown merchants or ambiguous descriptions, invoke Gemini Flash returning strict JSON schema:
       ```json
       {
         "category": "Gaming",
         "subcategory": "In-Game Purchases",
         "merchant_clean_name": "Steam",
         "confidence": 0.96,
         "tags": ["entertainment", "digital_goods"],
         "reasoning": "Transaction matches Valve digital distribution platform."
       }
       ```
  2. **Two-Step Threat & Policy Evaluation Engine**:
     - **Step 1: Fraudulent Entity / Blacklist Check**: Check merchant against known scam databases and high-risk categories (gambling, adult content, crypto on-ramps, predatory microtransactions, unverified digital key marketplaces).
     - **Step 2: Natural Language Policy Engine**: Take parent-defined plain-English rules (e.g., *"Flag any purchase over $25 on video games, any purchase made after 10 PM on school nights, or any transaction to unknown peer-to-peer sellers"*) and evaluate against transaction metadata. Return strict JSON schema:
       ```json
       {
         "is_flagged": true,
         "risk_level": "HIGH",
         "matched_rules": ["In-game purchase exceeding $25 threshold ($49.99 on Epic Games)"],
         "summary_for_parent": "Epic Games purchase of $49.99 exceeds your $25 gaming limit.",
         "requires_immediate_action": true
       }
       ```
  3. **Historical Learning & Reclassification**:
     - Implement `POST /api/transactions/{id}/reclassify` allowing parents to correct a transaction category.
     - Automatically update family-specific categorization embeddings and Redis cache to reflect parental corrections.
  4. **LLM Fallback & Latency Circuit Breaker**:
     - If the Gemini API experiences latency >500ms or rate limiting after 3 retries, fail over to the Tier-1 rule/keyword matching engine and queue background Celery tasks for asynchronous refinement.
     - Ensure total evaluation latency remains within the 1.5-second push notification window.
  5. **Policy Testing Simulator**: Implement an endpoint `POST /api/guardrails/simulate` allowing parents to test draft natural language rules against historical or mock transactions before saving.

---

### Module 3: Allowances, Category Budgets, Pre-Purchase Requests & Refund Reconciliation
- **Target Files**:
  - `backend/app/api/allowances.py` (Allowance scheduler, conditional rules, freeze/unfreeze)
  - `backend/app/api/budgets.py` (Category envelope management and balance tracking)
  - `backend/app/api/purchase_requests.py` (Pre-purchase request submission and approval workflow)
  - `backend/app/models/budget.py`
  - `backend/app/models/purchase_request.py`
  - `backend/app/services/paypal_service.py` (Payouts API, Orders & Vault API)
  - `backend/app/workers/celery_worker.py`
  - `backend/app/workers/celery_schedule.py` (Celery Beat periodic allowance triggers)
- **Subagent Instructions**:
  1. **Category-Wise Envelope Budgeting**:
     - Implement virtual envelope budgeting (e.g., Free Spend, Books/Education, Savings).
     - Spending is debited in real time from envelope balances; all amounts normalized to USD base currency in v1.
  2. **Automated Allowance Engine**:
     - Configurable recurring schedule (Weekly, Bi-weekly, 1st of month) using Celery Beat.
     - Disburse allowances via PayPal Payouts API (`POST /v1/payments/payouts`) directly to the child's PayPal address.
     - **Idempotency Guard**: Compute deterministic idempotency keys `(family_id, child_id, scheduled_date, allowance_id)` to prevent double disbursements during network retries.
  3. **Pre-Purchase Request Mode (Store Approvals)**:
     - Implement workflow: Child submits store URL, item name, and price $\rightarrow$ LLM inspects store & item against parent policies $\rightarrow$ Parent receives instant review card.
     - Upon parent approval, execute payout via PayPal Payouts or charge pre-approved payment tokens via PayPal Orders & Vault API.
  4. **Allowance Freeze on Incident Resolution**:
     - When a parent triggers `[Dispute / Freeze]` on a flagged transaction, automatically freeze upcoming scheduled allowance payouts until manually resumed.
  5. **Automated Refund Reconciliation**:
     - Listen to `PAYMENT.CAPTURE.REFUNDED` and `PAYMENT.SALE.REFUNDED` webhooks.
     - Extract `parent_payment_id`, locate the original debit entry in the database, restore the refunded balance back to the original category envelope, and set transaction status to `REFUNDED` or `PARTIALLY_REFUNDED` with attached `refund_id` (do not hard-delete ledger records).
     - Listen to `CUSTOMER.DISPUTE.RESOLVED` to update dispute states and restore/deduct balances accordingly.

---

### Module 4: Parent Web Dashboard (Next.js 14 Frontend)
- **Target Files**:
  - `frontend/app/page.tsx`
  - `frontend/app/dashboard/` (Family overview, balance totals, real-time activity stream)
  - `frontend/app/budgets/` (Category envelope progress bars, transaction ledger with refund filter)
  - `frontend/app/guardrails/` (Natural language policy editor)
  - `frontend/app/guardrails/simulator/` (Interactive rule-testing sandbox against sample transactions)
  - `frontend/app/requests/` (Pre-purchase request review with LLM risk summary and approve/deny actions)
  - `frontend/app/family/` (Family member management, co-parent/child invitation links)
- **Subagent Instructions**:
  1. Build a modern, responsive Tailwind/React dashboard with dark/light themes.
  2. **Real-Time Flagged Transaction Banner & Actions**:
     - High-priority alert banner with 1-click action triggers:
       - `[Approve]`: Clears flag and updates envelope spend.
       - `[Flag for Review]`: Prompts child for receipt upload or explanation.
       - `[Dispute / Freeze]`: Freezes upcoming allowances and opens modal with 1-click guidance to launch a PayPal dispute in the PayPal Resolution Center.
  3. **Rule Simulator UI**: Interactive playground allowing parents to draft natural language policies and test them against sample/historical transactions before activating.
  4. **Envelope Budget Management**:
     - Visual progress bars showing spend vs limit per category.
     - Transaction ledger table with an explicit toggle: **"Hide refunded transactions"**.
  5. **Pre-Purchase Request Review**: Interface showing pending child requests, item URLs, LLM threat analysis, and 1-click approve/reject actions.
  6. **Family Onboarding**: Interface to invite co-parents and children via email/invite links.

---

### Module 5: Family Mobile Companion App (React Native / Expo)
- **Target Files**:
  - `mobile/App.js`
  - `mobile/src/screens/HomeScreen.js`
  - `mobile/src/screens/EnvelopesScreen.js`
  - `mobile/src/screens/PurchaseRequestScreen.js`
  - `mobile/src/screens/ReviewActionScreen.js` (Receipt upload / kid explanation submission)
  - `mobile/src/screens/ParentAlertModal.js`
  - `mobile/src/navigation/`
  - `mobile/src/services/notifications.js` (FCM/APNs push notification integration)
- **Subagent Instructions**:
  1. Build a cross-platform mobile companion app supporting dual roles (Parent view & Child view).
  2. **Child View**:
     - Display personal allowance balance, virtual envelope spend progress, and transaction history.
     - **Purchase Request Form**: Interface to submit an item link, merchant name, amount, and note for parental approval.
     - **Review Action Screen**: If a parent triggers `[Flag for Review]`, the child receives a prompt to upload a receipt photo or type an explanation.
  3. **Parent View**:
     - Receive instant FCM/APNs push notifications when PayPal webhooks fire (<1.5 seconds turnaround).
     - Interactive push notification cards with 1-tap actions: `[Approve]`, `[Flag for Review]`, and `[Dispute / Freeze]`.

---

### Module 6: Security, Compliance, Testing & DevOps CI/CD
- **Target Files**:
  - `project_ver_1/.github/workflows/ci.yml`
  - `backend/app/security/` (AES-256 token encryption, VPC parental consent flows)
  - `backend/tests/test_webhooks.py`
  - `backend/tests/test_llm_schema.py`
  - `backend/tests/test_reconciliation.py`
  - `backend/tests/test_allowances.py`
- **Subagent Instructions**:
  1. **Financial Token Encryption & Security**:
     - Implement AES-256-GCM encryption for stored PayPal OAuth tokens, refresh tokens, and Vault tokens at rest.
  2. **COPPA Compliance**:
     - Implement FTC-compliant Verifiable Parental Consent (VPC) combining parent email verification and secure OAuth parental authorization before creating accounts for minors under 13.
  3. **Comprehensive Automated Test Suite**:
     - **Webhook Verification Tests**: Mock PayPal webhooks (capture, sale, refund, dispute) with valid and invalid cryptographic signatures.
     - **LLM Schema Validation Tests**: Unit test LLM categorization and policy evaluator using 50+ diverse transaction prompts (ensuring valid JSON schema and correct category assignment).
     - **Refund Reconciliation Test**: Verify that a $40 purchase followed by a $40 refund leaves the category envelope with the exact net balance of $0.
     - **Allowance Payout Idempotency Test**: Simulate concurrent / retry cron jobs to verify zero duplicate disbursements.
     - **Latency SLA Benchmark**: Ensure the webhook-to-notification pipeline executes within 1.5 seconds.
  4. **GitHub Actions CI**: Configure CI pipeline to execute linters, type checks, and pytest on pull requests.

---

## 3. Design Decisions & Resolution Summary

All open design clarifications have been resolved for version 1:
1. **PayPal Sandbox & Webhooks**: Handled via PayPal Developer Dashboard webhook simulators and API mock event triggers.
2. **LLM Fallback & Latency**: Automatic failover to Tier-1 rule/keyword matching after 3 retries or if Gemini API latency exceeds 500ms, with Celery async queueing.
3. **Multi-Currency Envelopes**: Version 1 strictly standardizes all family allowances, envelopes, and ledger entries in USD.
4. **COPPA Compliance**: FTC-compliant Verifiable Parental Consent (VPC) via parent email verification and secure OAuth parental authorization.
5. **Real-Time Strategy**: Hybrid model combining Pre-Purchase Request Mode (Pocket Money / In-App Store Approvals via PayPal Vault & Payouts) and Post-Capture Guardrails (instant webhooks within 1.5s).
6. **Audit Integrity**: Double-entry ledger with TimescaleDB; refunds update original debit entries to `REFUNDED` or `PARTIALLY_REFUNDED` without hard-deleting transactions.
