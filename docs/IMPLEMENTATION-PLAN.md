# Phased Implementation Plan

The platform was built in verifiable increments — each phase left the system
runnable and tested. This document records the plan, what shipped in each
phase, and the roadmap for the anticipated integrations.

## Phase 0 — Architecture & scaffolding ✅
- Repo layout (frontend / backend / powershell / docker / docs / tests).
- Decision: **IdentityProvider seam** so all features are demo-runnable and
  production swaps in PowerShell without touching callers.
- Configuration system (pydantic-settings, `EIO_*`), structured JSONL logging.
- *Verified by*: app boots, `/api/health`.

## Phase 1 — Core backend ✅
- Pydantic contracts (users, jobs, audit, auth), RBAC matrix, security
  primitives (PBKDF2, JWT cookies, CSRF, lockout).
- MockProvider with the seeded Northwind Dynamics tenant.
- *Verified by*: auth + RBAC test modules.

## Phase 2 — Validation, preview, jobs, audit ✅
- Identity derivation + full validation engine; ExecutionPlan builder;
  async job queue with SSE progress; SQLite audit store; clone merge policy;
  bulk importer (CSV/XLSX/JSON) and audit exporters (CSV/JSON/PDF).
- *Verified by*: end-to-end create/clone/bulk flow tests (34 tests total).

## Phase 3 — PowerShell automation layer ✅
- OnboardingCommon module (stdin-JSON contract, typed errors, mutex-guarded
  JSONL logs) + 16 production scripts (AD, Graph, EXO, home folders,
  profiles, validation, audit, stats).
- *Verified by*: Pester suite + version-independent smoke test (13 checks).

## Phase 4 — Frontend ✅
- Astro 5 + Tailwind 4 + strict TS. Pages: login, dashboard, create (dynamic
  1–50 forms), bulk, clone, logs, settings. Components: sidebar, header, OU
  tree picker, group picker, preview modal, SSE progress window, toasts,
  dark mode, reduced-motion support.
- *Verified by*: production build + full browser walkthrough.

## Phase 5 — Deployment & docs ✅
- Dockerfiles (backend, frontend+nginx with /api proxy & SSE buffering off),
  docker-compose; README + 8 guides.

## Phase 6 — Demo ✅
- Fantasy tenant seeded; browser-verified: created *John Doe* (Finance, E3,
  3 groups, mailbox, home folder) and cloned *John Smith* → *Fake Name*
  (9 groups, 2 licenses, shared mailboxes, proxy pattern, ext. attributes);
  audit trail and exports confirmed.

## Roadmap (architecture already accommodates)

| Integration | Attach point |
|---|---|
| ServiceNow / Jira onboarding tickets | New API route or poller producing `CreateUsersRequest`; reuse validation→preview→jobs |
| Workday / SAP HR feeds | `services/importer.py` header aliases already cover HR exports; add a scheduled fetcher |
| Graph-native provider | New `IdentityProvider` implementation; retire PowerShell per-capability |
| Intune enrollment, MFA, Conditional Access, BitLocker escrow | New job steps + scripts/Graph calls; step pattern (log→execute→audit→warn) generalizes |
| Teams / Slack / email notifications | Hook `JobManager._run` completion events |
| Azure Automation / hybrid workers | Swap `PowerShellRunner` transport (runbook/WinRM) behind the same JSON contract |
| Power Automate | Expose job webhooks; the REST API is already automation-friendly (CSRF-exempt token auth could be added for service principals) |
