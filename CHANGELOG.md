# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **On the version numbers below.** The repository carries no git tags yet, so the
> releases here were reconstructed from the commit history after the fact and the
> numbers were assigned retrospectively. They are accurate about *what changed and
> when*; they are not something you can `git checkout`. The first tag will be cut
> at the next release, and from that point this file is written as the work lands
> rather than afterwards.

## [Unreleased]

### Added

- A check that rejects AI-assistant attribution in commit messages: a
  `commit-msg` hook in `.githooks/` (enable with
  `git config core.hooksPath .githooks`) and a *Commit attribution* workflow that
  scans every commit reachable from each push and pull request. Both share
  `.github/scripts/check-attribution.sh`.
- `docs/lab.md`: an afternoon lab — stand up the stack, point it at a tenant,
  onboard a user, roll the user back, reset the tenant — with every command
  copy-pasteable, the expected output for each step, and timings measured from a
  fresh clone. It completes in demo mode with no directory at all, and states its
  non-goal: it is not a production deployment guide.
- Issue templates under `.github/ISSUE_TEMPLATE/`, including one shaped for
  "the lab broke at step N", plus links that route security reports and the
  hosted-demo login bounce away from public issues.
- `docs/api-pagination.md`: why `GET /api/users` cannot mirror the audit-log
  `limit`/`offset`/`total` pattern — neither LDAP paged results nor Microsoft Graph
  `/users` offers an offset or a cheap exact count — and the forward-cursor contract
  proposed instead, including keyset pagination for the one-process-per-call
  PowerShell provider
  ([#5](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/5)).
- `CONTRIBUTING.md`: demo-mode setup, the issues that are good entry points, the
  four architectural rules a reviewer will otherwise repeat, what a pull request should
  show, and the standing rule that no directory data ever enters this repository.
- `SECURITY.md`: private vulnerability reporting, the four demo defaults that must
  change before this touches a real directory, and the least-privilege service
  account model.
- MIT `LICENSE`, making the existing "MIT" claim in the README enforceable.

### Changed

- The README now opens with the lab's bounded promise, and no longer describes
  the platform as production-grade while its PowerShell layer is unvalidated
  against a real domain controller
  ([#3](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/3)).
- `SECURITY.md` pointed at a dry run of the offboarding path in `docs/` that did
  not exist; it now links chapter 4 of the lab, which is that dry run.

### Fixed

- A fresh clone's frontend no longer fails `npm run dev` with
  `Cannot find native binding`: `frontend/package-lock.json` is regenerated with
  rolldown's per-platform packages, and the workaround is gone from `docs/lab.md`
  ([#10](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/10)).
  Contributed by [@Jahnavi-HJ](https://github.com/Jahnavi-HJ) in
  [#11](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/pull/11).

### Known issues

The open issues that shape the next release, in the order they hurt a new user:

- Chrome blocks the GitHub Pages demo login, because the session cookie is
  cross-site and third-party cookies are now off by default
  ([#1](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/1)).
  Edge and Firefox work; Safari has the same problem via ITP.
- Nothing runs the test suites on push or pull request
  ([#2](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/2)).
- `EIO_SECRET_KEY` regenerates per process when unset, which silently logs everyone
  out on restart instead of failing loudly outside demo mode
  ([#9](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/9)).
- Jobs live in memory only, so a backend restart loses job history
  ([#4](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/4)).
- `GET /api/users` has a limit cap but no pagination
  ([#5](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/5)).
- The PowerShell layer passes its contract tests but has never been run against a
  real domain controller or M365 tenant
  ([#3](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/3)).
  If you have a lab, this is the single most valuable thing you could contribute.

## [0.2.0] — 2026-08-08

### Added

- **Offboarding module.** Disable one or many departing employees end to end:
  revoke licences, remove group memberships (distribution lists optionally kept for
  handover continuity), convert the mailbox to shared with an optional manager
  access grant, randomise the password, and optionally relocate the account to a
  disabled-users OU. It reuses the onboarding preview-and-approve gate and the same
  live progress stream, so nothing runs without an explicit approval.

### Fixed

- Documented the correct default frontend port in `astro.config.mjs`, which did not
  match the port the README told you to open.

## [0.1.0] — 2026-07-16

Initial release: the full onboarding platform.

### Added

- **Create 1–50 users** with dynamically generated forms covering identity,
  organisation, contact, address, groups, licences, mailboxes, password policy,
  home folder, roaming profile and logon script.
- **Clone an existing user** — copy OU, organisation, manager, address, groups,
  licences, shared mailboxes, proxy-address patterns, extension attributes, home
  folder and logon script from a template employee. Identity attributes (SID, GUID,
  password, username, email, employee ID, display name, personal data) are never
  copied, and the administrator chooses which families are.
- **Bulk import** from CSV, Excel (`.xlsx`) or JSON, with automatic header mapping
  for common HR-system exports.
- **Validation engine** — duplicate usernames, UPNs and emails against both the
  batch and the directory; invalid OU, manager or group; licence availability;
  password policy; naming convention; required fields. Derives `first.last`
  identities automatically and suffixes collisions.
- **Preview and approve** — a faithful per-user execution plan. Nothing runs until
  it is approved.
- **Live execution** — queued job engine with a progress bar, Server-Sent Event log
  streaming, per-user results, and one-time display of generated passwords, which
  are never persisted.
- **Audit trail** — who, what, when and where for every side effect, queryable and
  exportable as CSV, JSON or PDF.
- **Security** — Microsoft Entra ID sign-in (OIDC plus app roles) or demo-local
  accounts, four-tier RBAC (Helpdesk / HR / Administrator / Global Admin), httpOnly
  JWT session cookies with timeout, CSRF double-submit protection, login lockout,
  PBKDF2 password hashing, and secrets accepted only via environment or stdin.
- **Provider abstraction** — `PowerShellProvider` for production Active Directory
  and Entra ID, `MockProvider` for the seeded Northwind Dynamics demo tenant
  (23 users, 19 groups, 5 licence SKUs, an OU tree and shared mailboxes) behind the
  same interface, so the whole application is usable and testable with no directory.
- **Spanish UI translation** alongside English, with a Settings toggle. English is
  the default. Contributed by [@quickerup](https://github.com/quickerup) in
  [#7](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/pull/7).
- **Documentation set** — architecture, installation, administrator guide, API
  reference, PowerShell script contract and deployment guide under `docs/`.
- **Test suites** — pytest against the FastAPI app in demo mode, and a Pester 5
  suite plus a version-independent smoke test for the `OnboardingCommon` module.

[Unreleased]: https://github.com/juandresrodca/Enterprise-Onboarding-Platform/compare/bf73e6d...HEAD
[0.2.0]: https://github.com/juandresrodca/Enterprise-Onboarding-Platform/compare/e45386d...bf73e6d
[0.1.0]: https://github.com/juandresrodca/Enterprise-Onboarding-Platform/commits/0877c7c
