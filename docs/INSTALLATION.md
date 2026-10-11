# Installation Guide

## Prerequisites

| Component | Demo mode | Production |
|---|---|---|
| Python | 3.11+ | 3.11+ |
| Node.js | 20+ | 20+ (build only) |
| PowerShell | not needed | 7.x (`pwsh`) on a domain-joined Windows host |
| RSAT ActiveDirectory module | not needed | required |
| Microsoft.Graph modules | not needed | `Microsoft.Graph.Authentication`, `.Users`, `.Groups`, `.Identity.DirectoryManagement` |
| ExchangeOnlineManagement | not needed | required for mailbox features |
| Docker | optional | optional (see DEPLOYMENT.md) |

## Local setup (demo mode)

```bash
git clone https://github.com/juandresrodca/Enterprise-Onboarding-Platform.git
cd Enterprise-Onboarding-Platform

# 1. Backend
cd backend
python -m venv .venv
VPY="$PWD/.venv/bin/python"
[ -x "$PWD/.venv/Scripts/python.exe" ] && VPY="$PWD/.venv/Scripts/python.exe"
"$VPY" -m pip install -r requirements-dev.txt
cp .env.example .env                  # optional; demo works with defaults
"$VPY" -m uvicorn app.main:app --reload --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open **http://localhost:4321** and sign in with a demo account
(`gadmin` / `Demo!Pass123`). The Astro dev server proxies `/api` to
`127.0.0.1:8000`, so cookies remain same-origin.

### Resetting the demo tenant

Demo directory state persists to `backend/data/demo_state.json`. Delete that
file (and optionally `backend/data/audit.sqlite3`) and restart the backend to
reseed Northwind Dynamics.

## Docker (demo/evaluation)

```bash
docker compose up --build
# -> http://localhost:8080
```

## Verifying the installation

```bash
cd backend
VPY="$PWD/.venv/bin/python"
[ -x "$PWD/.venv/Scripts/python.exe" ] && VPY="$PWD/.venv/Scripts/python.exe"
"$VPY" -m pytest                                          # API/unit/integration tests
curl http://localhost:8000/api/health                       # {"status":"ok",...}
powershell -File powershell/tests/Invoke-SmokeTest.ps1      # module contract
```

## Switching to production mode

1. Provision the Windows execution host (see docs/DEPLOYMENT.md):
   PowerShell 7, RSAT, Graph + EXO modules, gMSA/service account with
   delegated OU rights.
2. `backend/.env`:
   ```
   EIO_DEMO_MODE=false
   EIO_ENVIRONMENT=production
   EIO_SECRET_KEY=<64 random chars>
   EIO_COOKIE_SECURE=true
   EIO_DOMAIN_DNS=corp.example.com
   EIO_UPN_SUFFIX=example.com
   EIO_ENTRA_TENANT_ID=... EIO_ENTRA_CLIENT_ID=... EIO_ENTRA_CLIENT_SECRET=...
   ```
3. Start the backend on the Windows host; on startup it runs
   `Connect-AD.ps1` and fails fast if the domain is unreachable.
4. Build the frontend (`npm run build`) and serve `dist/` from nginx/IIS with
   the `/api` proxy (see `docker/nginx.conf`).
