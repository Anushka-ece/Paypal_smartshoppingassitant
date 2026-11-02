# PennyPilot AI Security Remediation Report

## Status and scope

The requested backend security remediation is implemented and its automated
checks passed. This is not a security certification: no live PayPal service was
called, no production database was migrated, and the external Sandbox OAuth,
payment, token-refresh, and webhook flows still require end-to-end testing.
PayPal endpoints remain restricted to Sandbox.

## Issues identified and root causes

- **Authentication and authorization:** authentication helpers existed, but
  core financial API routes did not consistently require them. Several
  resource queries and writes were not scoped to the signed-in user's family.
- **OAuth account linking:** account identity and state were not reliably bound
  to the initiating signed-in user, and the prior token handling did not keep
  access and refresh tokens distinct.
- **Token storage and expiry:** encryption could fall back to a predictable
  value, while token expiry and refresh handling were incomplete.
- **Webhook processing:** mock verification needed to be explicitly confined
  to local/test environments; production verification must use PayPal's
  verification endpoint and reject replays.

## Implemented controls

### Authentication

- New passwords use Argon2id through `argon2-cffi`; existing scrypt hashes
  remain verifiable and are upgraded after successful login.
- JWTs are signed with HS256, expire after 30 minutes, validate issuer and
  expiration, and are checked against the current user and token version.
- Logout increments the user's token version, invalidating outstanding tokens.
- Login attempts are rate-limited through account lockout. Authentication
  fails closed when the JWT secret is missing, weak, or a known placeholder.
- Authenticated dependencies protect user-facing family, budget, guardrail,
  allowance, transaction, and purchase-request routes. Mutations check parent
  role and/or family ownership on the backend.

### Family ownership

- Reads and writes for family data are scoped to the authenticated user's
  family. Transaction access is scoped through its account; purchase,
  allowance, budget, and policy lookups are similarly family-scoped.
- Parent-only operations validate the current user's role. Client-supplied
  family IDs are not treated as authorization.
- Cross-family access and mutation attempts have regression coverage.

### PayPal OAuth and token handling

- OAuth initiation requires an authenticated parent, creates a random
  one-time state value, stores only its hash, binds it to the initiating user,
  and expires it after ten minutes. The callback consumes it atomically before
  exchanging the authorization code.
- The callback derives account ownership from the stored state and verified
  PayPal identity, rejects duplicate links, and does not trust a caller-supplied
  user ID.
- Access and optional refresh tokens are encrypted separately. The access
  token expiry is persisted; history sync refreshes near expiry and retries
  once after an authorization failure. Rotated refresh tokens are persisted.
- Refresh-token issuance is treated as response-dependent: the implementation
  stores and uses one only when PayPal actually returns a non-empty
  `refresh_token`. The local tests do not establish whether the configured
  PayPal consent/scopes issue one. Confirm this with a Sandbox consent flow;
  without one, the account must be relinked after the access token expires.
- Missing/invalid encryption configuration fails closed. PayPal API
  operations are restricted to `api-m.sandbox.paypal.com`.

### Webhooks and database

- The normal webhook path uses PayPal's webhook-signature verification
  mechanism and rejects invalid verification responses. Mock bypass requires
  the explicit local/test setting and is rejected in production. Processed
  event IDs are persisted to prevent duplicate event effects.
- Migration `0003_auth_and_paypal_oauth` adds token-version and token-expiry
  fields, OAuth state storage, and a uniqueness constraint for PayPal account
  IDs. It is reversible and does not intentionally delete existing records.

## Files changed for remediation

- Authentication, configuration, cryptography, and models:
  `requirements.txt`,
  `project_ver_1/backend/app/config.py`,
  `project_ver_1/backend/app/security/auth.py`,
  `project_ver_1/backend/app/security/crypto.py`,
  `project_ver_1/backend/app/models/user.py`,
  `project_ver_1/backend/app/models/account.py`,
  `project_ver_1/backend/app/models/paypal_oauth_state.py`,
  `project_ver_1/backend/app/models/__init__.py`.
- Routes and PayPal operations:
  `project_ver_1/backend/app/api/auth.py`,
  `project_ver_1/backend/app/api/family.py`,
  `project_ver_1/backend/app/api/budgets.py`,
  `project_ver_1/backend/app/api/guardrails.py`,
  `project_ver_1/backend/app/api/allowances.py`,
  `project_ver_1/backend/app/api/transactions.py`,
  `project_ver_1/backend/app/api/purchase_requests.py`,
  `project_ver_1/backend/app/api/webhooks.py`,
  `project_ver_1/backend/app/services/paypal_service.py`,
  `project_ver_1/backend/app/workers/celery_worker.py`.
- Migration, tests, and setup documentation:
  `project_ver_1/backend/migrations/env.py`,
  `project_ver_1/backend/migrations/versions/0003_auth_and_paypal_oauth.py`,
  `project_ver_1/backend/pyproject.toml`,
  `project_ver_1/backend/tests/conftest.py`,
  `project_ver_1/backend/tests/test_security_remediation.py`,
  `project_ver_1/backend/tests/test_security.py`,
  `project_ver_1/backend/tests/test_auth.py`,
  `project_ver_1/backend/tests/test_history_sync.py`,
  `project_ver_1/backend/tests/test_allowances.py`,
  `project_ver_1/backend/tests/test_purchase_requests.py`,
  `project_ver_1/backend/tests/test_webhooks.py`,
  `project_ver_1/backend/.env.example`,
  `project_ver_1/README.md`.
- The existing frontend OAuth and checkout-return flows were adjusted to pass
  authentication and return the signed checkout state:
  `project_ver_1/frontend/app/connect/page.tsx` and
  `project_ver_1/frontend/app/requests/page.tsx`.
- Responsive browser testing found that the shared header overflowed on narrow
  screens. The header now wraps and stacks at tablet/mobile widths in
  `project_ver_1/frontend/app/layout.tsx` and
  `project_ver_1/frontend/app/globals.css`.

## Validation results

| Check | Result |
|---|---|
| Complete backend test suite | **104 passed** (including the existing 92 tests); 482 warnings |
| Python syntax (`compileall`) | Passed |
| Python dependency consistency (`pip check`) | Passed; no broken requirements |
| Alembic upgrade, downgrade, and re-upgrade | Passed on a disposable SQLite database |
| TypeScript (`npm exec -- tsc --noEmit`) | Passed |
| Next.js production build | Passed with Next.js 15.5.28 |
| `npm audit` | 0 vulnerabilities |
| `git diff --check` | Passed |
| Production page HTTP smoke test | All 10 primary UI routes returned HTTP 200 |
| Responsive browser smoke test | No horizontal overflow on the 10 primary UI routes at 390px, 768px, and 1024px |
| Local backend HTTP smoke test | Health/root, unauthenticated 401, registration/login, authorized family read, and logout token invalidation passed against a temporary SQLite database |

The backend warnings include existing deprecation notices (including
`datetime.utcnow`, the installed Starlette/httpx test-client combination, and
the deprecated `google.generativeai` package). They did not fail the suite.
The frontend defines no standalone lint or test script; the successful Next.js
build completed its lint and type-check phase. The mobile package has only an
Expo `start` script and no installed dependencies or test/build script, so
mobile-specific execution was not validated.

## Remaining risks and manual actions

1. Configure distinct random `APP_JWT_SECRET` and `TOKEN_ENCRYPTION_KEY` values
   of at least 32 bytes in the backend environment. Do not copy the example
   placeholders, expose either value to the frontend, or rotate the encryption
   key without re-encrypting stored tokens.
2. Before applying the migration to an existing database, check for duplicate
   non-null `paypal_account_id` values. The unique index will fail rather than
   delete or merge duplicates.
3. Older tokens encrypted with the removed predictable fallback may be
   unreadable unless their original key is known; those accounts may need to
   reconnect. Do not restore or use a public fallback key.
4. Registration returns `pending_verification`, but no email-verification
   workflow exists and login does not enforce `is_verified`. Verification
   should not be represented as implemented.
5. Confirm refresh-token behavior for the actual Sandbox app/scopes and run
   end-to-end tests for consent, order approval/capture, token refresh, and
   webhook signature verification. Automated tests here do not prove external
   PayPal behavior.
6. This change does not add a complete refund-initiation or refund-amount
   history workflow. Passing tests alone do not establish that the service is
   secure or ready for real financial data.

No database was reset, no project database was migrated, and no commit or push
was created.
