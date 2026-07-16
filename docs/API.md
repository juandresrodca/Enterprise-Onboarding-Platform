# REST API Reference

Base path: `/api`. Interactive OpenAPI docs at `/api/docs`.

Authentication: session cookie (`eio_session`, httpOnly). All mutating
requests additionally require the `X-CSRF-Token` header mirroring the
`eio_csrf` cookie. Errors return `{"detail": ..., "code": ...}`.

## Auth

| Method & path | Permission | Description |
|---|---|---|
| `POST /auth/login` | public | Local login (demo mode). Body `{username, password}`. Sets session + CSRF cookies, returns `SessionInfo`. 429 after 5 failures/15 min. |
| `GET /auth/me` | session | Current session; sliding renewal. |
| `POST /auth/logout` | session | Clears cookies; audited. |
| `GET /auth/entra/login` | public | Redirects to Microsoft Entra ID (when configured). |
| `GET /auth/entra/callback` | public | OIDC redirect URI; maps app roles → platform roles. |

## Users & onboarding

| Method & path | Permission | Description |
|---|---|---|
| `GET /users?query=&limit=&recent=` | users:read | Search users (name, sam, email, department, title). |
| `GET /users/{sam}` | users:read | Full detail incl. groups, licenses, shared mailboxes, proxy addresses, extension attributes. |
| `GET /users/template.csv` | users:bulk | Bulk import CSV template. |
| `POST /users/validate` | users:read | Body `{users: NewUserSpec[]}` → `{valid, issues[], users[]}` with derived identities. |
| `POST /users/preview` | users:read | Validation + `ExecutionPlan` (per-user actions). |
| `POST /users/create` | users:create | Re-validates; 422 with issues if invalid, else **202** `{job_id}`. |
| `POST /users/bulk` | users:bulk | Multipart file (.csv/.xlsx/.json) → parsed users + full validation. Execution then goes through `/users/create`. |
| `POST /users/clone?execute=` | users:clone | Body `{source_sam, options, users[]}`. `execute=false` (default): merged users + issues + plan. `execute=true`: 202 `{job_id}`. |
| `POST /validate`, `POST /preview` | users:read | Spec-mandated aliases of the `/users/*` equivalents. |

`NewUserSpec` fields: `first_name*`, `last_name*`, `display_name`,
`sam_account_name`, `user_principal_name`, `email`, `ou*`, `department`,
`company`, `office`, `office_location`, `job_title`, `employee_id`,
`employee_type`, `cost_center`, `description`, `manager`, `phone`, `mobile`,
`country`, `city`, `state`, `address`, `postal_code`, `account_expiration`,
`groups[]`, `licenses[]`, `create_mailbox`, `shared_mailboxes[]`,
`proxy_addresses[]`, `extension_attributes{}`,
`home_folder{enabled, base_path, drive_letter}`,
`profile{roaming_profile_path, logon_script}`,
`password{generate, value, force_change_at_logon, never_expires}`.

## Directory

| Method & path | Permission | Description |
|---|---|---|
| `GET /ou` | directory:read | Full OU tree `[{name, dn, children[]}]`. |
| `GET /groups?search=&category=&limit=` | directory:read | Groups (security / distribution / m365). |
| `GET /licenses` | directory:read | SKUs with total/assigned counts. |
| `GET /shared-mailboxes` | directory:read | Shared mailboxes. |
| `GET /managers?query=` | directory:read | Manager autocomplete. |

## Jobs

| Method & path | Permission | Description |
|---|---|---|
| `GET /jobs?limit=` | jobs:read | Recent jobs (passwords redacted). |
| `GET /jobs/{id}` | jobs:read | Full job incl. one-time generated passwords. |
| `GET /jobs/{id}/events` | jobs:read | **Server-Sent Events**: `snapshot`, `log`, `progress`, `done`, `ping`. |

## Logs & audit

| Method & path | Permission | Description |
|---|---|---|
| `GET /logs?actor=&action=&status=&target=&date_from=&date_to=&limit=&offset=` | logs:read | Query audit entries + distinct action list. |
| `GET /logs/export?format=csv\|json\|pdf` | logs:export | Filtered export (max 10k rows); the export is itself audited. |

## Meta

| Method & path | Permission | Description |
|---|---|---|
| `GET /health` | public | Liveness + demo-mode flag. |
| `GET /dashboard` | dashboard:read | Aggregated stats, recent users/jobs/activity, errors 24h. |
| `GET /settings` | settings:read | Platform config + password policy. |
| `PUT /settings` | settings:write | Update password policy / naming regex; audited. |
