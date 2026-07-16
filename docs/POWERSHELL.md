# PowerShell Layer Reference

Target runtime: **PowerShell 7+** on a domain-joined Windows host.
Shared plumbing lives in `powershell/modules/OnboardingCommon/`.

## Contract with the backend

- **Input**: one JSON document on **stdin** (never argv — keeps passwords out
  of process listings and PowerShell operational event logs).
- **Output**: exactly one JSON object on stdout:
  ```json
  { "success": true, "data": { ... }, "error": null,
    "logs": [ { "ts": "...", "level": "INFO", "script": "...", "message": "..." } ] }
  ```
  On failure: `success:false` + `error:{code, message}`, exit code 1.
- **Diagnostics**: JSONL to `logs/powershell.jsonl` (mutex-guarded), never
  stdout.
- Every script uses `Invoke-OnboardingScript` which guarantees try/catch,
  the single-JSON-object rule, error codes (`Stop-Onboarding -Code ...`) and
  correct exit codes.

Run one manually:

```powershell
'{"query":"smith","limit":10}' | pwsh -NoProfile -File powershell/scripts/Get-Users.ps1
```

## Module functions (`OnboardingCommon`)

| Function | Purpose |
|---|---|
| `Invoke-OnboardingScript -Main {...}` | Standard wrapper: read params → run → emit result/exit code |
| `Read-OnboardingParams` / `Get-ParamValue` | Stdin JSON parsing + safe property access |
| `Out-OnboardingResult` | Emits the JSON contract (`-PassThru` for tests) |
| `Stop-Onboarding -Code -Message` | Terminating error with machine-readable code |
| `Write-OnboardingLog` | Buffered + JSONL structured logging |
| `Assert-ModuleAvailable` | Import-or-fail with `module_missing` code |
| `ConvertTo-OnboardingUser` | ADUser → normalized backend field names |

## Scripts

| Script | Params (JSON) | Does |
|---|---|---|
| `Connect-AD.ps1` | `{server?}` | Verifies AD reachability; returns domain/DC info. Run at backend startup (fail fast). |
| `Connect-Entra.ps1` | `{tenantId, clientId, certThumbprint?}` | App-only Graph session. Client secret comes from `EIO_GRAPH_CLIENT_SECRET` env, never a parameter. |
| `Get-Users.ps1` | `{query, limit, recentFirst}` | LDAP search (metachars escaped) → summaries. |
| `Get-User.ps1` | `{sam, expand}` | Full user: attributes, AD groups, Graph licenses + M365 groups, EXO shared-mailbox permissions (cloud lookups best-effort). |
| `Get-OUTree.ps1` | `{}` | Whole OU tree as nested nodes. |
| `Get-Groups.ps1` | `{search, category, limit}` | AD groups + Graph unified groups. |
| `Get-Stats.ps1` | `{}` | Dashboard counters. |
| `Create-ADUser.ps1` | `{user{...}, password}` | `New-ADUser` with the full attribute set, manager resolution, expiration, proxyAddresses & extensionAttributes via `-OtherAttributes`; duplicate guard. |
| `Clone-User.ps1` | `{sourceSam}` | Gathers the template user's copyable bundle (merge policy is enforced backend-side). |
| `Assign-Groups.ps1` | `{sam, groups[]}` | AD groups first; unresolved names attempted as M365 unified groups via Graph. Per-group failure report. |
| `Assign-Licenses.ps1` | `{action:"list"}` / `{action:"assign", sam, skus[]}` | `Get-MgSubscribedSku` / `Set-MgUserLicense`; sets UsageLocation from AD country; availability checks with precise error codes. |
| `Create-Mailbox.ps1` | `{action:"create"\|"grant-shared"\|"list-shared", ...}` | Hybrid `Enable-RemoteMailbox` (needs `remoteRoutingDomain`) or cloud license-driven provisioning; shared-mailbox FullAccess + SendAs. |
| `Create-HomeFolder.ps1` | `{sam, path, drive}` | UNC-only; `New-Item` + `icacls` Modify (OI)(CI) + `Set-ADUser -HomeDirectory/-HomeDrive`. |
| `Create-Profile.ps1` | `{sam, roaming_profile_path?, logon_script?}` | `Set-ADUser -ProfilePath/-ScriptPath`. |
| `Validation.ps1` | `{check: identity\|manager\|ou\|groups\|employeeId, ...}` | Server-side existence checks used by the validator. |
| `Audit.ps1` | `{entry{...}}` | Appends to the host-side `logs/audit-ps.jsonl` (SIEM pickup). |

## Attribute conventions

| Platform field | AD attribute |
|---|---|
| `cost_center` | `extensionAttribute10` (documented convention — adjust in `Create-ADUser.ps1` if your org uses another slot) |
| `employee_type` | `employeeType` |
| `office_location` | `physicalDeliveryOfficeName` |
| `account_expiration` | `AccountExpirationDate` (+1 day, so the account works through the stated end date) |
| `proxy_addresses` | `proxyAddresses` (`SMTP:` primary, `smtp:` secondary) |

## Required permissions

- **AD service account / gMSA**: delegated *Create/manage user objects* on
  the target OUs, *write members* on managed groups, share permissions on the
  home-folder root.
- **Graph app registration (app-only)**: `User.ReadWrite.All`,
  `Group.ReadWrite.All`, `Organization.Read.All`, `Directory.ReadWrite.All`.
- **Exchange Online**: `Exchange.ManageAsApp` + Exchange Recipient Management
  role for the app principal.

## Tests

- `powershell/tests/OnboardingCommon.Tests.ps1` — Pester 5 suite (no AD
  required): JSON contract, error codes, logging, serialization.
- `powershell/tests/Invoke-SmokeTest.ps1` — dependency-free smoke test that
  runs on Windows PowerShell 5.1 or 7+ (13 checks).
