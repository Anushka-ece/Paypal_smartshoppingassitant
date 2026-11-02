# PennyPilot AI

PennyPilot AI is a family-finance prototype that combines a FastAPI backend,
a Next.js frontend, PayPal Sandbox APIs, and Gemini-backed transaction
classification and policy guardrails with fallback behavior.
It includes family accounts, allowances, purchase requests, PayPal order
approval/capture, transaction history, and refund status derived from verified
PayPal webhook events.

## Current prototype limitations

This repository is a prototype, not a production-ready financial service.
PayPal operations are restricted to Sandbox; external Sandbox and Gemini
round-trips have not been verified as part of the local test run. Core
user-facing APIs now require backend authentication and enforce family
ownership. PayPal linking uses authenticated, one-time OAuth state and stores
tokens encrypted, but a real Sandbox consent, refresh, capture, and webhook
verification flow still needs end-to-end testing.

Registration currently returns `pending_verification`, but this project does
not yet provide an email-verification workflow and login does not enforce the
verification flag. Do not treat account verification as implemented.

The shopping-assistant/price-comparison feature and a complete refund
eligibility, amount-history, and refund-initiation workflow are not implemented.
The transactions screen can display a refund state and PayPal reference after a
verified webhook is processed, but does not show a separately persisted refund
amount. The budget screen contains illustrative sample data.

The authentication and PayPal token schema changes are applied with Alembic.
Before applying the migration to an existing database, check for duplicate
non-null PayPal account IDs; the new uniqueness constraint intentionally
rejects duplicates rather than deleting or merging account data.

## Architecture

- `backend/`: FastAPI API, SQLAlchemy models, Alembic migrations, PayPal service,
  Gemini service, webhook handlers, and Celery transaction-sync task.
- `frontend/`: Next.js app-router UI for login, purchase requests, transactions,
  budgets, and related family-finance screens.
- `../requirements.txt`: Python dependency manifest used by the backend.

The frontend talks to the backend using the configured API base URL. PayPal
client credentials, webhook configuration, and Gemini API keys belong only in
the backend environment; do not put secrets in frontend variables or commit
local `.env` files.

## Local Windows setup

Use the existing backend virtual environment if one is already present; do not
delete or recreate it. Run PowerShell from the repository root:

```powershell
Set-Location .\project_ver_1\backend
.\venv\Scripts\Activate.ps1
python -m pip install -r ..\..\requirements.txt
```

Configure backend values using the existing local `.env` and
`.env.example` as a reference. Keep PayPal pointed at Sandbox. If `.env`
already exists, do not overwrite it. Apply database migrations and start the
API:

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

`APP_JWT_SECRET` and `TOKEN_ENCRYPTION_KEY` must each be configured as distinct,
random values of at least 32 bytes. Generate each value separately in the
backend virtual environment, and place the outputs only in the local backend
`.env`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not reuse or rotate `TOKEN_ENCRYPTION_KEY` without a planned re-encryption
of stored PayPal tokens; old encrypted tokens cannot be read with a new key.

In another PowerShell window, install frontend dependencies and start Next.js:

```powershell
Set-Location .\project_ver_1\frontend
npm ci
npm run dev
```

If PowerShell cannot find `npm` but Node.js is installed in its default Windows
location, add it to the current session's PATH:

```powershell
$env:Path += ";C:\Program Files\nodejs"
```

The frontend is served at `http://localhost:3000`; the FastAPI docs are at
`http://localhost:8000/docs`. Restart an already-running Next.js process after
changing installed Next.js versions.

## Validation commands

From `project_ver_1\backend` with the virtual environment active:

```powershell
python -m pytest -q
python -m pip check
```

From `project_ver_1\frontend`:

```powershell
npm exec -- tsc --noEmit
npm run build
npm audit
```

The frontend currently has no dedicated lint or UI-test script configured.
Unit tests and mocked API tests do not establish that PayPal Sandbox or Gemini
works with external credentials.

## Demo guidance

Use only PayPal Sandbox buyer and merchant accounts, and clearly identify the
prototype limitations above. A purchase request can demonstrate backend order
creation, the returned PayPal approval link, and backend-verified capture
status. A refund state is visible only after a verified webhook event has been
processed. Do not represent static budget examples, mocked unit-test responses,
or an unverified external integration as live functionality.
