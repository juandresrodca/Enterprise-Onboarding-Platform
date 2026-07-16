# Enterprise Identity Onboarding Automation

A production-grade platform for onboarding one or many users into **Active
Directory / Microsoft Entra ID** environments (hybrid, Exchange Online,
Microsoft 365) from a web interface — with validation, preview/approval,
live execution progress and a full audit trail.

```
Astro + Tailwind + TypeScript          FastAPI (async, Pydantic)        PowerShell 7+
┌────────────────────────┐   REST    ┌──────────────────────────┐   JSON   ┌──────────────────────┐
│  Dashboard · Create    │ ───────►  │  Auth (Entra ID / RBAC)  │ ───────► │  ActiveDirectory     │
│  Bulk · Clone · Logs   │  ◄─SSE──  │  Validation · Preview    │  stdin/  │  Microsoft.Graph     │
│  Settings              │           │  Job queue · Audit       │  stdout  │  ExchangeOnlineMgmt  │
└────────────────────────┘           └──────────────────────────┘          └──────────────────────┘
                                                 │
                                     IdentityProvider interface
                                     ├── PowerShellProvider (production: AD / Entra ID)
                                     └── MockProvider      (demo mode: seeded fantasy tenant)
```

## Feature highlights

- **Create 1–50 users** with dynamically generated forms covering the full
  attribute set (identity, organization, contact, address, groups, licenses,
  mailboxes, password policy, home folder, roaming profile, logon script).
- **Copy existing user (clone)** — pick a template employee and copy OU,
  organization, manager, address, groups (security/distribution/M365),
  licenses, shared mailboxes, proxy-address patterns, extension attributes,
  home folder and logon script. Identity attributes (SID, GUID, password,
  username, email, employee ID, display name, personal data) are **never**
  copied; the administrator chooses which families to copy.
- **Bulk import** from CSV, Excel (.xlsx) or JSON with automatic header
  mapping for common HR-system exports.
- **Validation engine**: duplicate usernames/UPNs/emails (batch + directory),
  invalid OU/manager/group, license availability, password policy, naming
  convention, required fields — with automatic `first.last` identity
  derivation and collision suffixes.
- **Preview & approve**: a faithful execution plan of every action, per user.
  Nothing runs without explicit approval.
- **Live execution**: queued job engine with progress bar, streaming logs
  (Server-Sent Events), per-user results and one-time display of generated
  passwords (never persisted).
- **Audit**: who/what/when/where for every side effect, queryable and
  exportable as CSV, JSON or PDF.
- **Security**: Microsoft Entra ID sign-in (OIDC + app roles) or demo-local
  accounts, 4-tier RBAC (Helpdesk / HR / Administrator / Global Admin),
  httpOnly JWT session cookies with timeout, CSRF double-submit protection,
  login lockout, PBKDF2 password hashing, secrets via environment/stdin only.

## Quickstart (demo mode — no AD required)

The demo ships a seeded fantasy tenant (**Northwind Dynamics**: 23 users,
19 groups, 5 license SKUs, OU tree, shared mailboxes) behind the same
provider interface used in production.

```bash
# Backend (Python 3.11+)
cd backend
python -m venv .venv && .venv/Scripts/activate       # Windows
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000

# Frontend (Node 20+), second terminal
cd frontend
npm install
npm run dev                                           # http://localhost:4321
```

Or with Docker: `docker compose up --build` → http://localhost:8080

**Demo accounts** (password `Demo!Pass123`):

| Username   | Role          | Can do |
|------------|---------------|--------|
| `gadmin`   | Global Admin  | everything, incl. settings & policy |
| `admin`    | Administrator | create, bulk, clone, exports |
| `hr`       | HR            | create, bulk import |
| `helpdesk` | Helpdesk      | read-only (dashboard, users, logs) |

Try it: sign in as `gadmin` → **Create users** → onboard *John Doe* into
Finance → watch the live job → then **Clone user** with *John Smith* as the
template.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest          # 34 API/unit/integration tests
powershell -File powershell/tests/Invoke-SmokeTest.ps1 # module contract smoke test
Invoke-Pester powershell/tests                         # Pester 5 suite
```

## Repository layout

```
enterprise-onboarding/
├── frontend/        Astro 5 + Tailwind 4 + TypeScript SPA-style pages
├── backend/         FastAPI app (api/ services/ models/ core/) + pytest suite
├── powershell/      OnboardingCommon module + production scripts + tests
├── docker/          Dockerfiles + nginx config; docker-compose.yml at root
├── docs/            Architecture, installation, admin/dev guides, API, deployment
└── logs/            Structured JSONL logs (backend + PowerShell)
```

## Documentation

| Document | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, diagrams, provider abstraction, job engine, security model |
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Local setup, demo mode, prerequisites |
| [docs/ADMINISTRATOR-GUIDE.md](docs/ADMINISTRATOR-GUIDE.md) | Using every feature, roles, bulk template reference |
| [docs/DEVELOPER-GUIDE.md](docs/DEVELOPER-GUIDE.md) | Code layout, conventions, extending providers/endpoints |
| [docs/API.md](docs/API.md) | REST endpoints, permissions, payloads |
| [docs/POWERSHELL.md](docs/POWERSHELL.md) | Script contract, per-script reference, AD attribute conventions |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production topology, Entra app registration, HTTPS, hardening |
| [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md) | The phased build plan and future-integration roadmap |

## License / data note

All names, companies and identifiers in the demo dataset are fictional.
