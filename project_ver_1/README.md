# PennyPilot — Family Budgeting & Allowance Platform

Development scaffold for family budget tracking, allowance scheduling, transaction monitoring and purchase requests. Features are intentionally gated where the PayPal API or the required legal/security integrations do not support the proposed behavior.

## Project components

- `backend/`: FastAPI, SQLAlchemy, Alembic, Celery/Redis.
- `frontend/`: Next.js parent dashboard.
- `mobile/`: React Native / Expo family companion.
- `DEVELOPMENT_GUIDE.md`: module assignments and integration plan.

## Backend setup

1. From `project_ver_1/backend`, create a Python virtual environment and install the repository-root `requirements.txt`.
2. Copy `backend/.env.example` to `backend/.env`.
3. Set a random `APP_JWT_SECRET` of at least 32 bytes. Generate a Fernet key for `TOKEN_ENCRYPTION_KEY` before attempting PayPal account linking. Never commit `.env` or use development secrets in deployment.
4. Configure PayPal Sandbox app client credentials and `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`. Set the webhook URL and its registered PayPal webhook ID in `PAYPAL_WEBHOOK_ID`.
5. Set PayPal's registered return URL exactly to `PAYPAL_REDIRECT_URI`.
6. Initialize the database from `project_ver_1/backend` with `alembic upgrade head`.
7. Run the API from the repository root with Uvicorn using `--app-dir project_ver_1/backend`. For recurring payouts, run the Celery worker and beat processes after Redis is available.
8. Tests: `python -m pytest project_ver_1/backend/tests -q` from the repository root.

A parent registration remains unverified. There is deliberately no public endpoint to self-verify a parent; no child-account creation, co-parent invite delivery, or money-moving activity should be used with real people until those services are integrated and reviewed.

## PayPal API integration and constraints

- **OAuth identity**: Uses the real PayPal authorization-code exchange and OpenID Connect UserInfo API. This proves account identity/consent only; it is not permission to read personal consumer purchase history. Tokens are encrypted at rest; account linking is gated on an existing verified parent account.
- **Transaction Search**: The real `/v1/reporting/transactions` app-level request helper exists, but the application sync route is disabled (`501`) until PayPal confirms the required reporting approval and a safe account/family ownership mapping. It is not a consumer wallet aggregation API. PayPal reports that executed transactions may take up to three hours to appear, so it is not an instant-alert mechanism.
- **Webhooks**: Incoming messages require PayPal's signature verification API and a configured webhook ID. Event IDs are deduplicated. Events without a valid application `custom_id` mapping are ignored, never assigned to a default family. Captures are post-processing: this app cannot block or reverse an external checkout. Disputes are recorded when resolved; the app does not open disputes on the user's behalf.
- **Payouts**: Uses the PayPal Payouts v1 endpoint, fixed-decimal USD values and stable batch IDs for retries. Payouts are disabled by default (`PAYPAL_PAYOUTS_ENABLED=false`). Enabling them can move money. Use only a verified Sandbox recipient and test the full failure/retry path before considering any production setup.
- **LLM**: Uses Google's current `google-genai` SDK with deterministic keyword fallback after slow/error responses. Policy evaluation fails safe to review rather than silently approving an unknown policy case.
- **Currency**: Version 1 accepts USD only.

## Frontend and mobile setup

Node.js 20+ and npm are required. If `npm` is unavailable in PowerShell, install Node.js LTS and open a fresh terminal. From `project_ver_1/frontend`, run `npm install` then `npm run dev`. From `project_ver_1/mobile`, run `npm install` and `npm start`. On a physical phone/emulator, set `EXPO_PUBLIC_API_URL` to the backend's reachable LAN address, not `localhost`.

Frontend/mobile views now use API values for transactions and budgets; they do not represent actual PayPal balances. Mobile sign-in stores the bearer token in Expo SecureStore. Web uses tab-scoped sessionStorage. Logout clears these sessions.

## Production blockers

The app is not production-ready. Outstanding critical work includes verified email plus a legally reviewed verifiable parental-consent flow, child account authentication and access controls, secure email/push notification delivery, PayPal's approved account/reporting permissions, a compliant PayPal payment funding/checkout architecture, robust migrations and operational monitoring, rate limits, privacy/data retention policy, and full legal/security review. Do not collect real children's personal or financial data until COPPA and applicable laws are reviewed by qualified counsel. No LLM or parent action can synchronously approve or block unrelated PayPal checkout flows.
