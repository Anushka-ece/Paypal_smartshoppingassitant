# PennyPilot AI

PennyPilot AI is a family-finance prototype that brings together a FastAPI backend, a Next.js frontend, PayPal Sandbox APIs, and Gemini-based AI insights for family budgeting, spending guardrails, purchase approval flows, and transaction visibility.

## Project URL

GitHub repository: https://github.com/Anushka-ece/Paypal_smartshoppingassitant

## Demo-ready local setup

This project is designed to run locally for a working demo. If no public deployment is available, the correct way to present it is to share the repository link and provide local run instructions for judges or reviewers.

### 1) Backend setup

From the repository root in PowerShell:

```powershell
Set-Location .\project_ver_1\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r ..\..\requirements.txt
```

Create a local `.env` file by copying the example file and filling in the required values:

```powershell
Copy-Item .env.example .env
```

Use Sandbox values only, and set a valid random secret for both `APP_JWT_SECRET` and `TOKEN_ENCRYPTION_KEY`.

Then run the API:

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

The backend will be available at:
- http://localhost:8000
- API docs: http://localhost:8000/docs

### 2) Frontend setup

Open a second PowerShell window and run:

```powershell
Set-Location .\project_ver_1\frontend
npm install
npm run dev
```

The frontend will be available at:
- http://localhost:3000

### 3) Demo workflow

A working local demo can cover:
- user registration and login
- recording family expenses
- creating category budgets and tracking spending against them
- purchase approval workflow
- PayPal Sandbox checkout flow
- transaction and refund/status display

## Architecture

- `backend/`: FastAPI API, SQLAlchemy models, Alembic migrations, PayPal service,
  AI service, webhook handlers, and Celery transaction-sync task.
- `frontend/`: Next.js app-router UI for login, requests, transactions,
  budgets, and family-finance screens.
- `requirements.txt`: Python dependency manifest for backend installation.

## Prototype limitations

This project is a hackathon demo, not a production-ready financial service.
PayPal flows are restricted to Sandbox. The Render free plan may sleep while
idle, and its local SQLite database is temporary. Do not store important or
long-term family data in the public demo. Email verification, invitation
acceptance, and parental-consent verification are not implemented. Use test
data only. External PayPal and Gemini flows require valid credentials
configured privately in the deployment environment.

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
```

## Public judge demo on Render

The repository includes a Render Blueprint and Docker setup for one public
demo service. The frontend and backend share one URL; Next.js forwards API
requests to FastAPI inside the service. This avoids exposing the backend as a
separate public service.

The free Render plan is suitable for a hackathon demo, but it can sleep when
idle and its local SQLite database is temporary. Do not use it for important
or long-term family data. A Render URL is not active until the Blueprint has
been deployed successfully.

### Deploy

1. Commit and push the deployment files and app changes to the GitHub branch
   you want judges to review. Never commit `.env` files or credentials.
2. Sign in to Render, create a new Blueprint, and connect this GitHub
   repository. Select the pushed branch; Render will read `render.yaml`.
3. In Render's private environment-variable prompt, set distinct random
   `APP_JWT_SECRET` and `TOKEN_ENCRYPTION_KEY` values (at least 32 bytes each).
   Generate two separate values locally with
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   Copy PayPal Sandbox `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` from the
   PayPal Developer Dashboard. Never paste these values into GitHub or chat.
4. Add the Gemini API key as `GEMINI_API_KEY`. Without it, the application
   uses its rule-based fallback for supported AI-assisted checks.
5. Deploy the service and wait until Render reports it healthy. The intended
   URL is `https://pennypilot-ai-demo.onrender.com`; use the actual URL shown
   by Render if it differs.
6. If the assigned URL differs, update `ALLOWED_HOSTS`, `ALLOWED_ORIGINS`,
   `PAYPAL_REDIRECT_URI`, `PAYPAL_CHECKOUT_RETURN_URL`, and
   `PAYPAL_CHECKOUT_CANCEL_URL` in the Render environment using that URL,
   then redeploy.
7. In the PayPal Developer Dashboard, add `<public-url>/api/auth/paypal/callback`
   to the Sandbox app's return URLs. Create a Sandbox webhook at
   `<public-url>/api/webhooks/paypal` for the supported capture and refund
   events. Set `PAYPAL_WEBHOOK_ID` in Render to that webhook's ID and redeploy.
   The initial `pending-webhook-setup` value is only a deployment placeholder;
   webhook verification will not work until replaced with the real ID.
8. Open the public Render URL, register a demo family account, create a
   category budget, and record a matching expense to see the spending total
   update on the dashboard. Test payment actions with Sandbox buyer accounts
   only; no real-money transactions are supported.

### Local Docker smoke test

With Docker installed, run these commands from the repository root:

```powershell
docker build -t pennypilot-ai-demo .
docker run --rm -p 10000:10000 `
  -e APP_ENV=development `
  -e DATABASE_URL=sqlite:///./paypal_family_budget.db `
  -e APP_JWT_SECRET=local-demo-secret-change-before-use-123456 `
  -e TOKEN_ENCRYPTION_KEY=local-demo-encryption-key-change-123456 `
  pennypilot-ai-demo
```

Then open `http://localhost:10000`. This smoke test does not enable PayPal
linking; external features require valid Sandbox credentials configured
privately in the environment.

## Demo guidance

Use only PayPal Sandbox buyer and merchant accounts. A purchase request can
demonstrate backend order creation, the returned PayPal approval link, and
backend-verified capture status. Refund state is visible only after a verified
webhook event has been processed. Do not present static budget examples,
mocked responses, or unverified external integrations as live functionality.
