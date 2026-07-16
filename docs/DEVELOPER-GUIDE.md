# Developer Guide

## Code layout

```
backend/app/
├── main.py            app factory, middleware (CSRF, security headers), routers
├── config.py          pydantic-settings (env prefix EIO_), password policy
├── core/              rbac.py (permission matrix) · security.py (JWT, PBKDF2, CSRF)
│                      logging.py (JSONL) · exceptions.py (domain errors → HTTP)
├── models/            Pydantic contracts: user.py, job.py, audit.py, auth.py
├── services/
│   ├── provider.py    IdentityProvider ABC  ← the seam
│   ├── mock_provider.py / ps_provider.py / powershell.py (runner)
│   ├── validation.py  derivation + batch checks
│   ├── preview.py     ExecutionPlan builder
│   ├── clone.py       template-user merge policy
│   ├── jobs.py        queue, workers, SSE, per-step audit
│   ├── audit.py       SQLite store
│   ├── importer.py    CSV/XLSX/JSON → NewUserSpec
│   ├── exporter.py    audit → CSV/JSON/PDF
│   └── seed_demo.py   Northwind Dynamics fantasy tenant
└── api/               deps.py (DI + require(permission)) · routes_*.py

frontend/src/
├── layouts/AppLayout.astro     auth bootstrap, sidebar/header, theme
├── pages/*.astro               thin shells; logic in lib/pages/*.ts
├── lib/api.ts                  fetch wrapper (CSRF, 401 redirect, typed errors)
├── lib/components/             modal.ts (preview + SSE progress) · pickers.ts
│                               (OU tree, groups) · userform.ts (dynamic form)
└── lib/{session,theme,toast,dom,format,types}.ts
```

## Principles in force

- **Dependency Inversion**: nothing above `services/provider.py` knows which
  directory implementation is running. DI happens in `main.py` lifespan and
  flows through `api/deps.py` accessors.
- **Single validation path**: UI, bulk import and clone all funnel through
  `Validator.validate`; `/users/create` re-validates server-side regardless
  of what the client claims (defense in depth).
- **Jobs are the only writers**: every mutating directory call happens inside
  `JobManager._onboard_user`, which is also where auditing lives. Don't add
  write endpoints that bypass it.
- **No secrets on command lines or in logs** — PowerShell params go via
  stdin; passwords are excluded from job payload dumps and audit details.

## Common tasks

**Add a user attribute**
1. `models/user.py` → field on `NewUserSpec`.
2. `services/validation.py` if it needs checks/derivation.
3. `mock_provider.create_user` copy-list + `Create-ADUser.ps1` splat mapping.
4. `frontend/src/lib/components/userform.ts` (input + `getSpec`).
5. Extend `importer._ALIASES` for bulk import.

**Add an endpoint**
Route in `api/routes_*.py` with `Depends(require("<permission>"))`; add the
permission to `core/rbac.py`; audit side effects; add a pytest.

**Add an identity provider** (e.g. Graph-native)
Subclass `IdentityProvider`, wire selection in `main.py`. The full pytest
suite runs against any provider that honors the interface semantics.

## Conventions

- Python: type-hinted, async-first, domain errors via `OnboardingError`
  subclasses (mapped globally to HTTP), stdlib logging with `JsonFormatter`.
- PowerShell: `Set-StrictMode -Version Latest`, approved verbs, comment-based
  help, `Invoke-OnboardingScript` wrapper, `Stop-Onboarding` for typed errors.
- TypeScript: strict mode, no framework runtime — small `h()` DOM builder,
  contracts mirrored in `lib/types.ts`.
- CSS: Tailwind 4; component classes in `@layer components` (`.btn-*`,
  `.card`, `.input`, `.badge-*`); single accent palette; dark mode via
  `.dark` class; `prefers-reduced-motion` kill-switch; only
  transform/opacity are animated.

## Testing

```bash
cd backend && python -m pytest -q     # auth/CSRF/lockout, RBAC, validation,
                                      # e2e create/clone/bulk, exports, units
Invoke-Pester powershell/tests        # module contract
```

Tests run entirely in demo mode with isolated temp storage per test
(`tests/conftest.py`). When you touch the provider interface, run the flow
tests — they execute real jobs through the queue.
