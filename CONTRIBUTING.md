# Contributing

This platform creates, clones and disables accounts in Active Directory and Microsoft
Entra ID. That shapes how it is contributed to: **nothing in this repository needs a real
directory to develop against, and nothing in this repository should ever be tested
against one.** Demo mode is not a toy — it is the seam the whole architecture is built
around, and it is where your work happens.

If you have five minutes and want to help, the fastest useful contribution is to run the
demo, break something, and [tell us how](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/new).

---

## Get it running (demo mode, no AD required)

You need **Python 3.11+** and **Node 20+**. Nothing else — no domain controller, no
tenant, no Docker.

```bash
git clone https://github.com/juandresrodca/Enterprise-Onboarding-Platform.git
cd Enterprise-Onboarding-Platform

# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on Linux/macOS
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000

# Frontend, second terminal
cd frontend
npm install
npm run dev                     # http://localhost:4321
```

Sign in as `gadmin` and you are looking at **Northwind Dynamics**: 23 users, 19 groups,
5 licence SKUs, an OU tree and shared mailboxes, all served by `MockProvider`. Every
feature works against it — create, clone, bulk import, offboard, jobs, audit, exports.

`backend/.env.example` lists the settings; you do not need to copy it for demo mode.
[`docs/INSTALLATION.md`](docs/INSTALLATION.md) has the longer version, including Docker.

## Find something to work on

Start with the [open issues](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues).
Comment on the one you want before you start, so nobody duplicates your work. A few that
are self-contained enough to pick up cold:

| Issue | Why it is a good entry point |
|---|---|
| [#2](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/2) | A CI workflow for the two existing suites. No application code to understand. |
| [#5](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/5) | Pagination for `GET /api/users` — one route, one provider method, one table. |
| [#9](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/9) | Fail fast when `EIO_SECRET_KEY` is auto-generated outside demo mode. Small, and a real hardening win. |
| [#1](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/1) | The Pages demo login bounces in some browsers. Diagnosis is written up in [`docs/demo-login.md`](docs/demo-login.md); the fixes are not built. |

If you have an idea that is not listed, open an issue first. This is a platform with a
deliberately narrow remit, and a conversation beats a rejected pull request.

## How the codebase is arranged

[`docs/DEVELOPER-GUIDE.md`](docs/DEVELOPER-GUIDE.md) is the map: code layout, the
principles in force, the recipes for the common tasks (adding a user attribute, adding an
endpoint, adding a provider), and the per-language conventions. Read it before your first
pull request — it will answer most of what a reviewer would otherwise tell you.

Four rules from it are worth repeating here, because breaking one is the usual reason a
pull request stalls:

- **Nothing above `services/provider.py` knows which directory is behind it.** If your
  change makes the API layer aware of AD, PowerShell or Graph, it belongs behind the
  interface instead.
- **Jobs are the only writers.** Every mutating directory call happens inside
  `JobManager._onboard_user`, which is also where auditing lives. Do not add a write
  endpoint that bypasses it.
- **Validation is one path.** UI, bulk import and clone all funnel through
  `Validator.validate`, and `/users/create` re-validates server-side regardless of what
  the client claims. Adding a second, parallel check is how the two drift apart.
- **No secrets on command lines or in logs.** PowerShell parameters go via stdin;
  passwords are excluded from job payload dumps and audit details.

## Tests

```bash
cd backend && python -m pytest -q                        # 42 API/unit/integration tests
powershell -File powershell/tests/Invoke-SmokeTest.ps1   # module contract, no Pester needed
Invoke-Pester powershell/tests                           # Pester 5 suite
```

The pytest suite runs entirely in demo mode with isolated temporary storage per test
(`backend/tests/conftest.py` points `EIO_DATA_DIR` and `EIO_LOGS_DIR` at `tmp_path`), so
it leaves nothing behind and needs no configuration. When you touch the provider
interface, run the flow tests specifically — they execute real jobs through the queue.

The PowerShell suites cover the `OnboardingCommon` module contract: the JSON envelope, the
typed error codes, structured logging and AD serialisation. They do not need AD either.

Two honest gaps, in case you were looking for something to do:

- **There is no CI.** Both suites exist and neither runs automatically — that is
  [#2](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/2).
- **The frontend has no tests.** `npm run build` is the only gate, and it catches
  TypeScript errors rather than behaviour.

### What is deliberately not tested here

The production scripts under `powershell/scripts/` talk to `ActiveDirectory`,
`Microsoft.Graph` and `ExchangeOnlineManagement`. They are validated by hand against a
lab — see [#3](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/3)
and [`docs/POWERSHELL.md`](docs/POWERSHELL.md). **Do not write a test that expects a
directory to be present**, and do not point any part of this repository at a production
tenant to see what happens.

## Opening a pull request

Branch from `main`, keep the branch to one concern, and in the description say:

1. **What changed, and why.** Link the issue.
2. **What you ran.** The pytest and Pester output, and for anything user-facing, the
   screen you clicked through in the demo. The step people skip is looking at their own
   change in the browser, and it is the step reviewers notice.
3. **Whether it touches a write path.** If the answer is yes, say which job, which audit
   entry it produces, and which permission gates it.

Commits use [Conventional Commits](https://www.conventionalcommits.org/) —
`feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `test:`, `chore:` — because
[`CHANGELOG.md`](CHANGELOG.md) is assembled from them.

Add an entry to the `[Unreleased]` section of `CHANGELOG.md` for anything a user or
operator would notice. Internal refactors do not need one.

## Never put directory data in this repository

Not in an issue, not in a test fixture, not in a screenshot, not in a log excerpt. No real
usernames, UPNs, SIDs, group names, distinguished names or tenant IDs.

Every identifier in this repository is fictional and must stay that way: the seeded
Northwind Dynamics tenant exists only in `MockProvider`, and nothing here contains, or has
ever contained, data from a real directory. When you need to describe tenant shape in an
issue, send counts and structure — "1 400 users, 6-deep OU tree, 3 licence SKUs" — not
names.

Screenshots and reproduction steps should come from demo mode. If a bug only reproduces
against a real directory, describe it in those terms and redact; do not attach the
evidence.

## Security issues go privately

Do not open a public issue for a vulnerability. [`SECURITY.md`](SECURITY.md) has the
private reporting route, the response targets, and the four demo defaults that must change
before this platform touches a real directory.

## Code of conduct

Be straightforward and be kind. Assume the person on the other side of the review is
trying to make the same thing work as you are. Harassment of any kind, or any behaviour
that would make a colleague uncomfortable in a professional setting, is not welcome.
Report a problem to **juandresrodca@gmail.com**.

## Licence

Contributions are licensed under the [MIT Licence](LICENSE), the same as the project.
