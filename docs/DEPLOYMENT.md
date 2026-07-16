# Deployment Guide

## Topologies

**Demo / evaluation** — anywhere Docker runs:

```bash
docker compose up --build     # frontend :8080 (nginx, proxies /api), backend demo mode
```

**Production (hybrid AD)** — the backend must run where PowerShell can reach
the domain:

```
                     HTTPS (TLS termination: ingress / LB / IIS ARR)
Users ──────────► nginx / IIS  ── static frontend (dist/)
                      │  /api proxy
                      ▼
        Windows member server (domain-joined)
        ├── FastAPI backend (EIO_DEMO_MODE=false), run as gMSA
        ├── PowerShell 7 + RSAT AD + Graph + EXO modules
        └── line of sight to DCs, file server (home folders)
```

Run the backend as a Windows service (e.g. [NSSM] or `sc.exe` wrapping
`uvicorn app.main:app --host 127.0.0.1 --port 8000`), identity = the gMSA.

## GitHub Pages demo (free hosting)

Static frontend on GitHub Pages + free backend on Render, in demo mode:

1. **Backend on Render** (free web service): root directory `backend`,
   build `pip install -r requirements.txt`,
   start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, env vars:
   ```
   EIO_DEMO_MODE=true
   EIO_COOKIE_SECURE=true
   EIO_COOKIE_SAMESITE=none          # cookies must cross sites (Pages -> Render)
   EIO_SECRET_KEY=<64 random chars>
   EIO_CORS_ORIGINS=["https://<user>.github.io"]
   ```
2. **GitHub Pages**: repo Settings → Pages → Source = *GitHub Actions*; add
   repo variable `API_BASE_URL` = the Render URL. Pushing to `main` runs
   `.github/workflows/deploy-pages.yml`, which builds with
   `PUBLIC_BASE_PATH=/<repo>` and `PUBLIC_API_BASE` and deploys `dist/`.

Notes: Render's free tier sleeps after ~15 min idle (first request takes
~30–60 s to wake). Cross-site cookies (`SameSite=None`) are blocked by
Safari's tracking prevention — use Chrome/Edge/Firefox for the Pages demo, or
host frontend + API same-origin (Docker/nginx) for full compatibility.

## Microsoft Entra ID app registration (sign-in)

1. **App registrations → New**: web platform, redirect URI
   `https://onboarding.example.com/api/auth/entra/callback`.
2. **App roles** (create, value must match `EIO_ENTRA_ROLE_MAP` defaults):
   `Onboarding.GlobalAdmin`, `Onboarding.Administrator`, `Onboarding.HR`,
   `Onboarding.Helpdesk` — assignable to users/groups.
3. **Enterprise application → Users and groups**: assign your admin groups to
   the roles. Users without a role are rejected at sign-in (and audited).
4. Client secret (or better, certificate) → store in your vault; expose to
   the backend as `EIO_ENTRA_CLIENT_SECRET`.
5. Backend `.env`:
   ```
   EIO_ENTRA_TENANT_ID=<tenant guid>
   EIO_ENTRA_CLIENT_ID=<app guid>
   EIO_ENTRA_CLIENT_SECRET=<from vault>
   EIO_ENTRA_REDIRECT_URI=https://onboarding.example.com/api/auth/entra/callback
   EIO_DEMO_MODE=false
   ```

## Graph / Exchange app (automation, separate registration)

App-only permissions with admin consent: `User.ReadWrite.All`,
`Group.ReadWrite.All`, `Organization.Read.All`, `Directory.ReadWrite.All`,
`Exchange.ManageAsApp` (+ Exchange *Recipient Management* role assignment).
Prefer **certificate** auth (`certThumbprint` param of `Connect-Entra.ps1`);
if a secret must be used it is read from `EIO_GRAPH_CLIENT_SECRET` only.

## Service account (on-prem AD)

Use a **gMSA** where possible. Delegate, at the target OUs only:
create/delete user objects, write all user properties, reset password; write
`member` on managed groups; NTFS/share rights on the home-folder root.
Do **not** use a Domain Admin.

## Configuration checklist (production)

| Variable | Value |
|---|---|
| `EIO_DEMO_MODE` | `false` |
| `EIO_SECRET_KEY` | 64+ random chars from your vault (stable across restarts) |
| `EIO_COOKIE_SECURE` | `true` (enables HSTS emission too) |
| `EIO_CORS_ORIGINS` | exactly your frontend origin(s) |
| `EIO_SESSION_TIMEOUT_MINUTES` | per your policy (default 30) |
| `EIO_DOMAIN_DNS` / `EIO_UPN_SUFFIX` / `EIO_DEFAULT_HOME_BASE_PATH` | your environment |
| `EIO_SCRIPT_TIMEOUT_SECONDS` / `EIO_MAX_CONCURRENT_SCRIPTS` | tune for DC capacity |

## HTTPS

Terminate TLS at your standard ingress (IIS ARR, nginx, Azure App GW).
The backend emits `Strict-Transport-Security` when `EIO_COOKIE_SECURE=true`;
`X-Content-Type-Options`, `X-Frame-Options` and `Referrer-Policy` are always
set. Keep the `/api` proxy **same-origin** with the frontend so the httpOnly
session cookie never needs third-party settings.

## Hardening checklist

- [ ] Demo mode off; demo accounts therefore disabled (they exist only in demo mode).
- [ ] Entra sign-in enforced; app roles assigned via groups; MFA/Conditional Access on the enterprise app.
- [ ] gMSA with least-privilege OU delegation; no interactive logon.
- [ ] Secrets only via env/vault; confirm nothing sensitive in `logs/*.jsonl`.
- [ ] `logs/` + `backend/data/audit.sqlite3` shipped to SIEM and backed up.
- [ ] Firewall: backend reachable only from the frontend proxy.
- [ ] Patch cadence for PowerShell modules (Graph SDK, EXO v3).
- [ ] Restore test: audit DB + demo-state/product config.

## Upgrades

Backend and frontend are stateless apart from `backend/data/`; deploy
blue/green behind the proxy. Run `pytest` + `Invoke-Pester` in CI before
promoting. Database migrations: the audit schema is created idempotently at
startup.
