# Lab: AD / Entra onboarding, end to end, in an afternoon

By the end of this lab you will have run a complete identity-onboarding pipeline
on your own machine and watched every stage of it happen: a new hire is
**validated** against the directory, turned into a **plan** you read before
anything runs, **provisioned** with groups, a licence and a mailbox by a queued
job, written to an **audit trail**, and then **rolled back** — disabled, stripped
of access, mailbox handed to their manager — and finally the whole tenant reset to
where it started.

All of it runs against **Northwind Dynamics**, a fictional 23-person tenant served
by `MockProvider`. You need no domain controller, no Microsoft 365 tenant and no
cloud account. Every command is copy-pasteable, and every chapter says what you
should see.

## What this lab is not

**It is not a production deployment guide.** It runs on four deliberately
insecure demo defaults, and it does nothing to harden them. They are named, with
what each one costs you in production, in
[SECURITY.md → What the demo defaults are, and are not](../SECURITY.md#what-the-demo-defaults-are-and-are-not).
Read that before you point any part of this platform at a directory you care
about, and do not point it at a production tenant at all.

It also does not prove the PowerShell layer works against real Active Directory.
That layer passes its contract tests but has not yet been run against a real
domain controller — which is what
[issue #3](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/3)
is open for. Chapter 2 explains how to help with it, if you have a lab of your own.

## Chapters

| # | Chapter | Your time (estimate) | Machine time (measured) |
|---|---|---|---|
| 0 | [Prerequisites](#0-prerequisites) | 5–15 min | — |
| 1 | [Stand up the stack](#1-stand-up-the-stack) | 10 min | ~75 s of installs |
| 2 | [Point it at a tenant](#2-point-it-at-a-tenant) | 5 min | — |
| 3 | [Onboard a user](#3-onboard-a-user) | 20–30 min | ~5 s |
| 4 | [Roll it back](#4-roll-it-back) | 15–20 min | ~5 s |
| 5 | [Clean up](#5-clean-up) | 2 min | — |

Machine times were measured once, on Windows 11 with Python 3.11.1, Node 22.16
and a home broadband connection, from a fresh clone on 1 October 2026. Your
installs will be faster or slower; the shape will not change. The estimates for
*your* time assume you read each plan rather than skim it — reading the plan is
the point. Allow 60–90 minutes in total, which is where *an afternoon* comes from.

If a step does not do what this page says it will,
[open a "The lab broke at step N" issue](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/new?template=lab-step.yml).
That report is the most useful thing this page can produce.

---

## 0. Prerequisites

Stated once, here, and assumed by every chapter after it:

| You need | Check with | Notes |
|---|---|---|
| Python **3.11 or later** | see below | older versions are not supported |
| Node **20 or later** | `node --version` | |
| git and curl | `git --version`, `curl --version` | |
| A bash shell | — | Git Bash on Windows; the default shell on Linux and macOS |
| Ports 8000 and 4321 free | — | backend and frontend respectively |
| About 300 MB of disk | — | roughly 100 MB of Python packages, 200 MB of `node_modules` |

Many machines have more than one Python. Find the command that prints 3.11 or
later and keep it in a variable, because every Python command in this lab uses
it:

```bash
PY=python3        # or: python, or: py -3.11 on Windows — whichever prints 3.11+
$PY --version
```

**On Windows, clone somewhere with a short path**, such as `C:\src`. Windows
limits paths to 260 characters unless long-path support is enabled, and Python's
own packaging tools nest deep enough to cross that from a folder that is already
around 190 characters long — the failure shows up as `ensurepip` exiting with
`WinError 3`.

## 1. Stand up the stack

Clone the repository:

```bash
git clone https://github.com/juandresrodca/Enterprise-Onboarding-Platform.git
cd Enterprise-Onboarding-Platform
```

Create the backend's virtual environment and install into it. This lab never
*activates* the environment; it calls the environment's own interpreter by path,
which works identically on every platform:

```bash
$PY -m venv backend/.venv
VPY="$PWD/backend/.venv/bin/python"
[ -x "$PWD/backend/.venv/Scripts/python.exe" ] && VPY="$PWD/backend/.venv/Scripts/python.exe"
"$VPY" -m pip install -r backend/requirements.txt
```

> Why use the interpreter directly? Running `.venv/Scripts/activate` as a command
> does not activate the environment in the current shell. Activation requires
> `source .venv/Scripts/activate` in Git Bash, or `source .venv/bin/activate` on
> Linux/macOS. Calling `"$VPY"` directly avoids depending on activation or on
> whichever `python` and `pip` happen to be on `PATH`.

Start the backend and leave this terminal running:

```bash
cd backend && "$VPY" -m uvicorn app.main:app --port 8000
```

You should see `DEMO MODE: using in-memory Northwind Dynamics directory` in the
log output. In a **second terminal**, from the repository root, install and start
the frontend:

```bash
cd frontend
npm install
npm run dev
```

You should see `astro … ready in …` and a local URL of `http://localhost:4321/`.

Open `http://localhost:4321/` and sign in with any demo account — `gadmin`,
`admin`, `hr` or `helpdesk`, all with the password `Demo!Pass123`. They exist
only in demo mode; [SECURITY.md](../SECURITY.md#out-of-scope) explains why they
are published.

> Running locally, the frontend and the API share an origin through the dev
> server's `/api` proxy, so the session cookie is first-party and sign-in just
> works. **If you are using the hosted demo on GitHub Pages instead and it sends
> you back to the login screen**, that is a cross-site cookie policy, not a broken
> login: [docs/demo-login.md](demo-login.md) explains it in thirty seconds.

## 2. Point it at a tenant

The platform never talks to a directory directly. It talks to an
`IdentityProvider`, and which one it gets is decided by a single setting,
`EIO_DEMO_MODE`. That is the whole of "pointing it at a tenant".

### 2A. The fictional tenant (the lab path)

You are already there: `EIO_DEMO_MODE` defaults to `true`. Open a **third
terminal** at the repository root. Define the helpers that chapters 3 and 4 use —
they keep a cookie jar, attach the CSRF token the API requires on every write,
and pull single fields out of JSON responses using the Python you already have:

```bash
VPY="$PWD/backend/.venv/bin/python"
[ -x "$PWD/backend/.venv/Scripts/python.exe" ] && VPY="$PWD/backend/.venv/Scripts/python.exe"
API=http://127.0.0.1:8000/api
JAR="$(mktemp)"
field() { "$VPY" -c 'import json, sys
d = json.load(sys.stdin)
for k in sys.argv[1:]:
    d = d[int(k)] if isinstance(d, list) else d[k]
print(d)' "$@"; }
post() { curl -s -b "$JAR" -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' -d @"$2" "$API$1"; }
wait_job() { while :; do
  s=$(curl -s -b "$JAR" "$API/jobs/$1" | field job status); echo "$s"
  case $s in queued|running) sleep 1 ;; *) break ;; esac; done; }
```

Sign in as the Administrator — the lowest role that may both onboard and offboard:

```bash
CSRF=$(curl -s -c "$JAR" -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Demo!Pass123"}' \
  "$API/auth/login" | field csrf_token)
curl -s -b "$JAR" "$API/auth/me" | field role_label
```

Then confirm which tenant you are pointed at, and how big it is:

```bash
curl -s "$API/health" | field demo_mode
curl -s -b "$JAR" "$API/dashboard" | field stats total_users
```

You should see `Administrator`, then `True`, then `23`. Keep that last number in
mind; chapters 3 and 4 move it.

### 2B. A real test tenant (optional, and unvalidated)

Skip this unless you already have an isolated test domain — a single-DC lab, or a
Microsoft 365 developer tenant — and want to help with
[#3](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/3).
Building such a lab is not part of the afternoon.

Be clear about what you are doing: **nobody has yet run this path end to end.**
The production provider runs PowerShell 7 scripts on a domain-joined Windows
host with the `ActiveDirectory`, `Microsoft.Graph` and `ExchangeOnlineManagement`
modules. The settings to change are listed in
[docs/INSTALLATION.md → Switching to production mode](INSTALLATION.md#switching-to-production-mode),
the permissions the service account needs are in
[docs/POWERSHELL.md → Required permissions](POWERSHELL.md#required-permissions),
and on startup the backend runs `Connect-AD.ps1` and refuses to start if the
domain is unreachable.

Two differences from the lab path matter for the chapters below:

- **The demo accounts do not exist outside demo mode**, so the `curl` sign-in in
  2A will fail. Sign in through Microsoft Entra ID in the browser, and follow
  chapters 3 and 4 using the "in the browser" route.
- **Rolling back disables; it does not delete.** Chapter 4's final reset deletes
  the fictional tenant's state file. On a real directory there is no such file,
  and removing the account is a manual step outside this tool
  (`Remove-ADUser -Identity jane.doe` on your test domain, once you have checked
  what chapter 4 did).

Whatever happens, report it on #3 or with the lab issue template. Send counts and
structure, never names — the rule in
[CONTRIBUTING.md](../CONTRIBUTING.md#never-put-directory-data-in-this-repository)
applies to lab reports too.

## 3. Onboard a user

You will onboard **Jane Doe** as a Financial Analyst reporting to John Smith, with
two groups, a Microsoft 365 E3 licence and a mailbox. Describe her once, in a
request file:

```bash
cat > jane.json <<'EOF'
{"users": [{
  "first_name": "Jane", "last_name": "Doe",
  "ou": "OU=Finance,OU=Company,DC=northwind,DC=local",
  "department": "Finance", "job_title": "Financial Analyst",
  "manager": "john.smith",
  "groups": ["SG-Finance-Users", "DL-Finance"],
  "licenses": ["SPE_E3"], "create_mailbox": true
}]}
EOF
```

Note what is *not* in the file: a username, a UPN, an email address or a
password. Those are derived or generated, which is the next step.

### 3.1 Validate

```bash
post /users/validate jane.json > validated.json
field valid < validated.json
field users 0 sam_account_name < validated.json
field users 0 user_principal_name < validated.json
```

You should see `True`, `jane.doe` and `jane.doe@northwind.com`. The validator
derived the identity from the naming convention, then checked it against the
directory for duplicates, and checked the OU, the manager, both groups and the
licence pool exist. Change `"manager"` to someone who does not exist and run it
again to see what a failure looks like — `valid` turns `False` and the issue names
the field.

### 3.2 Read the plan

```bash
post /users/preview jane.json | field summary
```

You should see `1 user(s) will be onboarded with 4 total actions`: create the
account, add the groups, assign the licence, provision the mailbox. **Nothing has
happened yet.** The preview-and-approve gate is the central safety property of
the platform; [SECURITY.md](../SECURITY.md#in-scope) calls a path around it the
highest-severity bug the repository could have.

### 3.3 Approve and execute

```bash
JOB=$(post /users/create jane.json | field job_id)
wait_job "$JOB"
```

You should see `running`, possibly more than once, then `completed`. The create
endpoint re-validated the request before queueing it — the server never trusts
that the client validated first.

### 3.4 Check the result

```bash
curl -s -b "$JAR" "$API/users/jane.doe" | field user enabled
curl -s -b "$JAR" "$API/users/jane.doe" | field user licenses
curl -s -b "$JAR" "$API/users/jane.doe" | field user groups
curl -s -b "$JAR" "$API/logs?target=jane.doe" | field total
curl -s -b "$JAR" "$API/dashboard" | field stats total_users
```

You should see `True`, `['SPE_E3']`, `['SG-Finance-Users', 'DL-Finance']`, `4`
and `24`. The four audit entries are one per side effect — account, groups,
licence, mailbox — each recording who did it, from where, and as part of which
job.

### In the browser

The same chapter, through the UI: **Create users** → generate one form → fill in
Jane Doe, *Browse* for the Finance OU, type `john.smith` as manager, *Select
groups* → **Validate** → **Preview & execute** → read the plan → **Approve**.
The progress window streams the job's log as it runs. Then open **Audit logs**
and filter by target `jane.doe`.

## 4. Roll it back

Onboarding someone by mistake — wrong start date, wrong person, a cancelled
offer — is ordinary, and the way out should be as deliberate as the way in.
Here it is the offboarding flow, behind the same plan-then-approve gate.

### 4.1 Read the rollback plan

```bash
cat > rollback.json <<'EOF'
{"users": [{"sam_account_name": "jane.doe", "reason": "Lab rollback"}],
 "options": {"grant_mailbox_access_to": "john.smith"}}
EOF
post /offboard/preview rollback.json | field summary
```

You should see `1 user(s) will be offboarded with 5 total actions`: disable the
account and randomise its password, remove its group memberships, revoke its
licences, convert its mailbox to a shared one with access for John Smith, and
record the reason.

### 4.2 Approve and execute

```bash
JOB=$(post /offboard rollback.json | field job_id)
wait_job "$JOB"
curl -s -b "$JAR" "$API/users/jane.doe" | field user enabled
curl -s -b "$JAR" "$API/users/jane.doe" | field user licenses
curl -s -b "$JAR" "$API/users/jane.doe" | field user groups
curl -s -b "$JAR" "$API/logs?target=jane.doe&action=user.offboard" | field total
```

You should see `running`, `completed`, then `False`, `[]`, `['DL-Finance']` and
`1`. Jane can no longer sign in and holds no licence. She is still on the
distribution list, on purpose: by default offboarding keeps distribution lists so
that mail addressed to a team does not bounce during a handover. Set
`"remove_from_groups": true, "keep_distribution_lists": false` in `options` to
strip those too.

Notice what did **not** happen: the account still exists. Offboarding disables,
which is reversible and auditable; deleting is a retention-policy decision the
platform leaves to the organisation.

### 4.3 Reset the tenant completely

A restart alone undoes nothing — the fictional tenant is saved to disk so the
demo survives restarts. To return Northwind Dynamics to its 23-person seed, stop
the backend with **Ctrl+C** in the first terminal, then from the repository root:

```bash
rm -f backend/data/demo_state.json backend/data/audit.sqlite3
```

Start the backend again exactly as in chapter 1. Back in the third terminal, sign
in again — the demo signs sessions with a key generated per process, so your old
session ended with the old process — and count:

```bash
CSRF=$(curl -s -c "$JAR" -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Demo!Pass123"}' \
  "$API/auth/login" | field csrf_token)
curl -s -b "$JAR" "$API/dashboard" | field stats total_users
```

You should see `23`, and `GET /api/users/jane.doe` now returns a 404. The
per-process signing key is one of the four demo defaults; SECURITY.md explains why
it would log your users out on every restart in production.

### In the browser

**Offboard users** → search `jane` → add her → optional reason → under
*Grant mailbox access to*, type `john.smith` → **Preview offboarding** →
**Approve & execute**. The reset in 4.3 has no browser equivalent.

## 5. Clean up

Stop both servers with **Ctrl+C**. From the repository root:

```bash
rm -f jane.json validated.json rollback.json
```

Everything else the lab created lives inside the clone — `backend/.venv`,
`backend/data/`, `frontend/node_modules` and `logs/` — and is ignored by git.
Delete the clone to remove all of it.

## Where to go next

- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — the provider seam you switched in
  chapter 2, and the job engine that ran chapters 3 and 4.
- [docs/API.md](API.md) — every endpoint the `curl` commands used, and the ones
  they did not.
- [CONTRIBUTING.md](../CONTRIBUTING.md) — the issues that are good first
  contributions, and what a pull request should show.
- [Issue #3](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/3)
  — if you have a test domain, chapter 2B against it is the most valuable thing
  anyone can contribute to this repository right now.
