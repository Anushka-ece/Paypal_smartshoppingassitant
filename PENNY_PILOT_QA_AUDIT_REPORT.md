# PennyPilot AI QA and Hackathon Readiness Audit

## Executive assessment

**Status: local prototype builds and its automated backend suite passes, but the
project is not ready to expose publicly or present as a verified end-to-end
PayPal/AI integration.** The most important blocker is missing backend
authentication and family-ownership authorization on core APIs. OAuth account
linking and refresh-token use also have unresolved gaps. No live PayPal Sandbox
or Gemini requests were made, so mocked tests are not evidence of external
integration success.

The existing PayPal and frontend work was preserved. No commit, push, deploy,
live payment, or database reset was performed. Environment values were not
printed.

## Scope and implementation performed

Inspected the backend API, auth and PayPal services, webhook handling, data
models/migrations, worker, tests, frontend routes, package manifests, build
configuration, and setup documentation. The repository already contained
uncommitted PayPal integration changes.

Audit-specific changes:

| File | Change |
|---|---|
| `project_ver_1/backend/app/workers/celery_worker.py` | Historical sync now returns an explicit error when the account has no PayPal token instead of silently substituting a mock token and producing example transactions. |
| `project_ver_1/backend/tests/test_history_sync.py` | Added a regression test that verifies missing-token sync creates no transactions. |
| `project_ver_1/frontend/package.json` and `package-lock.json` | Updated Next.js to 15.5.28 after validating the Next 14 dependency issue; React 18 was retained. |
| `project_ver_1/backend/app/main.py`, `app/config.py`, `tests/test_security.py` | Production configuration validation is run on application initialization and rejects placeholder credentials and a non-Sandbox PayPal API host; regression tests cover these checks. |
| `project_ver_1/README.md` | Replaced the scaffold text with Windows setup, validation commands, demo guidance, and explicit limitations. |
| `project_ver_1/frontend/next-env.d.ts` | Next.js regenerated its tracked route-type declarations during the build. |

Other uncommitted PayPal, webhook, payout, checkout, transaction/refund UI,
login, and request-management changes predated this final audit phase and were
preserved. The existing `diff-summary.txt` was also preserved.

## Findings and readiness blockers

| Priority | Finding | Evidence / impact | Required next step |
|---|---|---|---|
| **Critical** | Core APIs do not enforce user authentication or family ownership. | For example, purchase-request listing and creation accept caller-supplied family/child IDs in `backend/app/api/purchase_requests.py` (around lines 62-103); allowance, budget, guardrail, transaction, and family routes have the same general issue. The family router imports auth helpers but its member and invitation handlers do not depend on them. Callers can access or mutate other families' records if IDs are known or guessed. | Add authenticated route dependencies and enforce that every requested family/account/resource belongs to the current user. Add cross-family denial tests and update clients to send the existing auth token. Do not expose this backend publicly before this is fixed. |
| **High** | PayPal account linking is not bound to the signed-in user. | The connect page calls `/auth/login` without a user ID or OAuth state. The callback stores tokens only when it can resolve a target user from `user_id` or `state` (`backend/app/api/auth.py`, around lines 99-150 and 180-210). The UI redirect therefore does not prove that consent links the intended account. | Generate and validate unguessable OAuth state associated with the authenticated user; bind the callback to that state, not a client-supplied user ID. Test both successful and mismatched-state flows. |
| **High** | The user OAuth refresh-token helper is not integrated into historical transaction sync. | The OAuth callback stores `refresh_token or access_token` in `paypal_encrypted_token` (`backend/app/api/auth.py`, around lines 165-180). The sync worker passes the decrypted value to the Reporting API as a bearer access token (`backend/app/workers/celery_worker.py`, around lines 57-75). Although `PayPalService.refresh_access_token` exists (`backend/app/services/paypal_service.py`, around lines 117-146), this sync path does not call it. Linked-account history sync may therefore fail when a refresh token is stored or an access token expires. | Store token type/expiry explicitly, refresh before Reporting API calls when required, encrypt refreshed tokens, and test refresh success, expiry, and failure. |
| **High** | Registration verification is not enforced during login. | Registration returns `pending_verification`, but the login path does not require the account to be verified. | Enforce verification before issuing a session, or implement the intended verification flow and tests. |
| **High** | Real external integrations were not exercised. | PayPal order/capture, payout, webhook-verification, and Gemini unit tests use mocks. No external Sandbox/Gemini calls were made; the project must not claim they have been live-verified. | In a controlled local environment, complete a Sandbox-only buyer approval/capture and a configured webhook verification test. Test Gemini only with a valid backend key. Never use live-money credentials. |
| **Medium** | Refund functionality is status reconciliation, not a complete refund workflow. | Refund status/reference can be displayed after a verified webhook, but there is no complete refund eligibility check, dedicated refund amount/history, or refund-initiation flow. | Implement and test the missing refund workflow before advertising refunds as supported. |
| **Medium** | The AI shopping-assistant/price-comparison feature is absent. | Gemini is used for transaction classification and policy guardrails with fallback behavior; no shopping assistant or price comparison was found. | Implement the promised shopping experience or clearly scope it out of the submission description and demo. |
| **Medium** | The budget UI includes illustrative sample data. | The Budgets page labels its examples as illustrative; it should not be presented as live family budget data. | Connect it to verified backend data or keep the static-data disclosure visible in the demo. |
| **Low** | No frontend lint or UI-test scripts are configured. | `npm run` lists only `dev`, `build`, and `start`. TypeScript and production build checks are available, but no frontend test framework is present. | Add focused UI/API integration tests and a lint script when the frontend behavior is stabilized. |
| **Low** | Backend emits deprecation warnings. | The successful test run reports Starlette/httpx, `google.generativeai`, and `datetime.utcnow()` deprecations. | Schedule compatibility updates; these warnings did not fail current tests. |

## Dependency audit

- The reported Next.js 14.2.35 dependency tree was reproduced in an isolated
  temporary copy. `npm audit` identified a **critical direct `next` advisory**
  affecting versions `9.5.0` through `15.5.27`; the audit advertised a
  breaking-major fix at Next.js 16.4.4.
- The original installation output reported one additional high-severity
  advisory, but its package/advisory details were not retained. The isolated
  reproduction, which used the currently patched dependency set apart from
  Next.js, did not reproduce that second finding. No unverified package
  attribution is made here.
- The frontend was moved to Next.js **15.5.28**, preserving React 18. The final
  `npm audit` reported **0 vulnerabilities**.
- Final resolved frontend versions: Next.js 15.5.28, React 18.3.1,
  TypeScript 5.9.3, `@types/react` 18.3.31, and `@types/node` 20.19.43.
- No broad dependency upgrade or `npm audit fix --force` was used.

## Validation results

| Check | Result |
|---|---|
| Backend full test suite | **PASS** — 92 passed, 320 warnings in 27.11 seconds. |
| Frontend TypeScript | **PASS** — `npm exec -- tsc --noEmit`. |
| Frontend production build | **PASS** — Next.js 15.5.28 compiled and generated all 15 static pages. |
| Frontend dependency audit | **PASS** — `npm audit` found 0 vulnerabilities. |
| Python dependency consistency | **PASS** — `pip check` reported no broken requirements. |
| Python syntax compilation | **PASS** — `compileall`. |
| Database migration validation | **PASS** — Alembic upgrade against in-memory SQLite; the project database was not reset. |
| Local route smoke checks | **PASS** — backend `/` and `/docs`, and frontend `/`, `/login`, `/transactions`, and `/requests` returned HTTP 200 in the recorded local checks. |
| `git diff --check` | **PASS** at audit validation; rerun after any additional edits. |
| Frontend lint/UI tests | **NOT CONFIGURED** — no lint or test script exists. |
| Live PayPal Sandbox/Gemini | **NOT TESTED** — no external calls were made. |

The frontend uses Node.js 26.13.0 and npm 11.20.0 in the recorded environment.
PowerShell did not initially find `npm` in a fresh shell; adding
`C:\Program Files\nodejs` to that shell's `PATH` allowed all frontend checks to
complete. The existing Next.js dev server should be stopped and restarted after
the dependency upgrade; the prior process was not stopped automatically.

## Hackathon criteria assessment

- **PayPal integration:** **PARTIAL / NOT LIVE-VERIFIED.** Sandbox order
  creation, approval URL handling, capture, payout, and webhook paths are
  implemented and tested with mocks. Account-linking and refresh-token gaps
  remain, and no Sandbox transaction was executed.
- **AI:** **PARTIAL / NOT LIVE-VERIFIED.** Gemini-backed classification and
  policy guardrails with fallback behavior exist. No shopping assistant or
  price-comparison implementation was found.
- **Working prototype:** **PARTIAL.** The app builds, local routes respond, and
  the backend automated suite passes. This does not resolve the authorization
  blocker or prove external services work.
- **Documentation:** **IMPROVED.** `project_ver_1/README.md` documents setup,
  validation, demo guidance, and known limitations.
- **Public repository / official rules:** **NOT VERIFIED.** A Git remote is
  configured, but repository visibility and rule compliance were not
  independently verified.
- **Demo video:** **NOT VERIFIED.**

## Recommended release gate

Do not expose the app publicly or describe it as a complete family-finance
service until backend authentication/ownership checks and OAuth state binding
are fixed and covered by tests. Then run a controlled PayPal Sandbox approval,
capture, cancellation, webhook, and payout-failure walkthrough. Clearly
identify unimplemented refunds/shopping features and static budget examples in
the submission text and demo.
