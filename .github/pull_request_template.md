<!--
Thanks for contributing to the Enterprise Onboarding Platform.

Three things worth knowing before you read the checklists:

1. **One automated check runs here, and it does not look at your code.**
   *Commit attribution* scans every commit message reachable from this pull
   request and fails on AI-assistant trailers. The test suites are not wired up —
   that is still
   [#2](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/2).
   So a green tick below means **a person ran something and is saying so**, which
   is why the sections ask you to paste output rather than to describe it.
2. **Most of this template is deletable.** A typo fix, a broken link or a doc that
   got clearer needs **What this changes** and nothing else. Delete the rest.
3. **This platform writes to real directories.** Nothing here should ever have
   been pointed at one. The declaration near the bottom is not a formality.

The long reference for all of it is
[CONTRIBUTING.md](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/blob/main/CONTRIBUTING.md)
and
[docs/DEVELOPER-GUIDE.md](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/blob/main/docs/DEVELOPER-GUIDE.md).
Where this template and those pages disagree, the pages win.
-->

## What this changes

<!-- One or two sentences on why it matters rather than a restatement of the diff. -->

Closes #

**Layer:** <!-- API (backend/) · Web UI (frontend/) · PowerShell (powershell/) · Deployment · Documentation -->

## What you ran

<!-- Delete this section only for a documentation-only change. -->

Paste the output. "Tests pass" is not the output, and the difference between the
two is most of what a reviewer here is doing.

```bash
cd backend

# The environment's own interpreter, by path — no activation, every platform
VPY=.venv/bin/python; [ -x .venv/Scripts/python.exe ] && VPY=.venv/Scripts/python.exe

"$VPY" -m pytest -q
powershell -File powershell/tests/Invoke-SmokeTest.ps1
Invoke-Pester powershell/tests
```

- [ ] `pytest -q` — output pasted below, including the count
- [ ] The PowerShell suites, if this touches `powershell/` — output pasted below
- [ ] `npm run build`, if this touches `frontend/` — it is the only gate there, and it catches TypeScript rather than behaviour

<details><summary>Output</summary>

```text

```

</details>

## Did you look at it in the demo?

<!-- Delete this section if nothing user-facing changed. -->

Sign in as `gadmin` against **Northwind Dynamics** — 23 users, 19 groups, 5 licence
SKUs, served entirely by `MockProvider`. No domain controller, no tenant.

- [ ] I clicked through the screen this change affects and it did what I expected
- [ ] A screenshot is attached, **from demo mode**, if the change is visual

The step people skip is looking at their own change in the browser, and it is the
step reviewers notice.

## If it touches a write path

<!-- Delete this section if it does not. -->

Every mutating directory call goes through `JobManager._onboard_user`, which is
also where auditing lives.

- [ ] Which job runs it, and which audit entry it produces, are named above
- [ ] Which permission gates it is named above
- [ ] Nothing above `services/provider.py` learned which directory is behind it
- [ ] Validation still goes through `Validator.validate` — no second, parallel check
- [ ] No secret reaches a command line, a job payload dump or an audit detail

## No directory data — code, tests, issues, screenshots, log excerpts

This one is not deletable, and it covers more than the diff.

- [ ] **Nothing in this pull request contains real usernames, UPNs, SIDs, group names, distinguished names or tenant IDs** — not in code, not in a test fixture, not in a screenshot, not in a pasted log excerpt, not in the description above

Every identifier in this repository is fictional and must stay that way. When you
need to describe the shape of a real tenant, send counts and structure — "1 400
users, 6-deep OU tree, 3 licence SKUs" — not names. If a bug only reproduces
against a real directory, describe it in those terms and redact; do not attach the
evidence.

**If directory data has already reached a branch, an issue or a screenshot, stop
and use the private route** —
[Security → Report a vulnerability](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/security/advisories/new),
or **juandresrodca@gmail.com** if that is unavailable to you. It gets removed.
A public issue about it spreads it further.

## Everything

- [ ] A line under **[Unreleased]** in [`CHANGELOG.md`](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/blob/main/CHANGELOG.md) for anything a user or operator would notice — internal refactors do not need one
- [ ] Any new command block calls the interpreter by path (the `VPY` line above), not a bare `python` — [#14](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/14) and [#16](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/16) are both that drifting
- [ ] Conventional Commit subjects in the imperative — `CHANGELOG.md` is assembled from them
- [ ] No AI-assistant attribution in any commit message. Turn on the hook once per clone with `git config core.hooksPath .githooks`; the *Commit attribution* workflow fails the pull request otherwise
- [ ] The branch is one concern

## Anything a reviewer should know

<!--
A test you could not get to fail, a provider behaviour that surprised you, a
decision you went back and forth on, or a piece of this you are not happy with yet.
With no test CI to lean on, this is the most useful part of the description.

Arguing that the design is wrong is welcome; open an issue first if it is large.
House style, for reference: British spelling in prose, LF and the encodings
`.gitattributes` decides, and Conventional Commit subjects in the imperative.
-->
