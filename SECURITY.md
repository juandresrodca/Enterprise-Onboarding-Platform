# Security Policy

This platform creates, clones and disables accounts in **Active Directory and
Microsoft Entra ID**. A bug here does not corrupt a file — it provisions an
account nobody approved, or it leaves a leaver enabled. That is a different
class of blast radius from most web applications, and it is why this policy
spends as much space on *running it safely* as on *reporting a flaw in it*.

## Reporting a vulnerability

**Do not open a public issue for a security problem, and never paste directory
data — real usernames, UPNs, SIDs, group names, tenant IDs — into an issue.**

Report privately through GitHub:
[Security → Report a vulnerability](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/security/advisories/new).
If private reporting is unavailable to you, email **juandresrodca@gmail.com**
with `Onboarding security` in the subject.

Please include:

- which layer is affected — the API (`backend/`), the SPA (`frontend/`), the
  PowerShell module (`powershell/`), or a deployment of your own,
- the request you sent and the response you got, verbatim, with identifiers
  redacted,
- whether you reproduced it in **demo mode** (`MockProvider`) or against a real
  directory, and if the latter, whether it was your own lab,
- what you expected instead, and what an attacker gains.

What to expect:

| Stage | Target |
|---|---|
| Acknowledgement | 72 hours |
| Initial assessment | 7 days |
| Fix or documented mitigation | 90 days, sooner where the severity warrants |
| Credit | given in the release notes unless you ask otherwise |

This is a personal open-source project maintained outside working hours. There
is no bug bounty; there is a genuine commitment to answering you.

## Supported versions

Development happens on `main`, and the GitHub Pages demo tracks it. Fixes land
on `main`; there are no maintained release branches. If you forked or vendored
this into your own tooling, the hardening in *Before you point it at a real
directory* became yours to maintain at that moment.

## In scope

- **Privilege escalation across the four roles.** Helpdesk is read-only, HR may
  create and bulk-import, Administrator may clone and export, Global Admin may
  change settings. Any request that performs an action the caller's role does
  not carry is a finding. The rules live in
  [`backend/app/core/rbac.py`](backend/app/core/rbac.py).
- **Bypassing the preview-and-approve gate.** Nothing is supposed to touch a
  directory without an explicit approval step. A path that executes a plan the
  operator never approved is the highest-severity bug in this repository.
- **Injection into the PowerShell layer.** Parameters are passed as a single
  JSON document on **stdin**, never on the command line, precisely so that a
  crafted display name or OU cannot become an argument. A payload that escapes
  that contract and reaches the shell, or that traverses out of
  `powershell/scripts/` via a script name, is a finding.
- **Session and CSRF handling.** Forging or replaying the `eio_session` JWT,
  defeating the double-submit CSRF check in
  [`backend/app/main.py`](backend/app/main.py), or fixing a session across a
  login.
- **Leaking a generated password.** Passwords are displayed once and are not
  meant to reach a log line, the audit trail, an export or a job record. Any
  path where one persists is a finding.
- **Audit tampering.** An action that succeeds without an audit entry, or an
  entry that can be altered through the API.
- A dependency advisory affecting `backend/requirements.txt` or
  `frontend/package.json`.

## Out of scope

- **Anything reachable only with Global Admin.** That role is designed to change
  settings and run bulk operations; using it to do so is the product working.
- **The demo accounts.** `gadmin` / `admin` / `hr` / `helpdesk` with the password
  `Demo!Pass123` are published in the README on purpose. They exist only when
  `EIO_DEMO_MODE` is true, and `_build_local_accounts()` returns nothing when it
  is false. Finding them in the demo is not a finding; finding them in a
  deployment means that deployment was never configured (see below).
- **Missing hardening you control** — no TLS, no reverse proxy, no rate limiting
  in front of the API, an over-broad `EIO_CORS_ORIGINS`.
- **The third-party-cookie demo failure.** Chrome blocking the cross-site session
  cookie on the Pages demo is a known deployment characteristic, tracked in
  [#1](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/1),
  not a vulnerability.
- **In-memory job state.** Jobs and their results do not survive a backend
  restart. That is a durability gap, tracked in
  [#4](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/4).
- Findings produced only by an automated scanner, with no working request behind
  them.

## What the demo defaults are, and are not

The shipped configuration in [`backend/app/config.py`](backend/app/config.py) is
tuned for *clone it and it runs*, not for your production. Four defaults are
deliberately insecure for that reason, and every one of them is a single
environment variable away from correct:

| Default | Value out of the box | Why it is wrong in production |
|---|---|---|
| `EIO_DEMO_MODE` | `true` | Serves the fictional Northwind tenant through `MockProvider` and enables the four published local accounts. Nothing reaches a real directory until this is `false`. |
| `EIO_SECRET_KEY` | a fresh `secrets.token_urlsafe(48)` per process | Sessions do not survive a restart, and **two uvicorn workers sign with two different keys**, so a session minted by one is rejected by the other. Set a stable value from your vault. |
| `EIO_COOKIE_SECURE` | `false` | The session cookie is sent over plain HTTP. Set `true` the moment you are behind TLS. |
| `EIO_CORS_ORIGINS` | `localhost:4321` | Harmless locally, but `allow_credentials=True` is set, so widening this to `*` — or to an origin you do not control — hands your sessions away. Never use a wildcard here. |

`docs/DEPLOYMENT.md` is the authority on the full set; this table exists so the
four that matter most are not buried in it.

## Before you point it at a real directory

- **Authenticate with Entra ID, not local accounts.** Set `EIO_ENTRA_TENANT_ID`,
  `EIO_ENTRA_CLIENT_ID` and `EIO_ENTRA_CLIENT_SECRET`, and map app roles rather
  than maintaining a second user store.
- **Give the service account the least privilege that works.** It needs to create
  and modify the user objects in the OUs you target, and nothing else. Delegate
  at the OU, do not use Domain Admin because it is quicker. The Graph and
  Exchange permissions are enumerated in `docs/POWERSHELL.md`.
- **Put the API behind a reverse proxy with TLS and rate limiting.** The login
  lockout (`EIO_LOGIN_MAX_ATTEMPTS`, five attempts then fifteen minutes) is a
  brute-force speed bump on one endpoint, not a rate limiter for the API.
- **Secrets come from the environment or stdin. Never commit a `.env`.** The
  PowerShell runner exists in the shape it does — JSON on stdin,
  `-NoProfile -NonInteractive` — so that credentials never appear in a process
  listing, a command-line audit event, or PowerShell transcription.
- **Read `logs/` before you ship it.** Structured JSONL is written for both
  layers. Decide where it goes, who can read it, and how long you keep it; it
  records who provisioned whom.
- **Test the offboarding path in a lab first.** It disables accounts, revokes
  licences, strips group memberships and randomises passwords. `docs/` walks
  through a dry run, and issue
  [#3](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/3)
  tracks validating the module against a real hybrid lab.

## `-ExecutionPolicy Bypass`

The runner invokes PowerShell with `-ExecutionPolicy Bypass`. This is
intentional and is not a vulnerability report: the scripts are files the operator
has already installed on the server, execution policy is not a security boundary
(Microsoft documents it as a safety feature, not a control), and the alternative
is a deployment that silently fails on a locked-down host. What protects this
surface is that script names are resolved and traversal-checked in
`PowerShellRunner.script_path()`, and that parameters never reach the command
line.

## Responsible testing

Test against the demo tenant or a lab you own. Provisioning or disabling accounts
in a directory you have not been authorised to test is unauthorised access under
the Criminal Justice (Offences Relating to Information Systems) Act 2017 in
Ireland, the Computer Misuse Act 1990 in the United Kingdom, and equivalent
legislation elsewhere — and unlike a web bug, it is immediately visible to the
people whose accounts you touched.

The [MIT licence](LICENSE) disclaims warranty. This policy states intent.
