# Paginating `GET /api/users`

Background for [#5](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/5).
That issue says to mirror the audit-log pattern. This page is why that cannot be done
as written, and what the contract should be instead.

Nothing here is implemented yet. It exists so the decision is made once, in the open,
rather than three times in three pull requests.

## Where things stand

`GET /api/users` takes a cap and returns everything under it:

```http
GET /api/users?query=smith&limit=50&recent=false
```

```json
{ "users": [ … ], "count": 12 }
```

`count` is the length of the array, not the size of the result set. `limit` is clamped
to 500 in [`routes_users.py`](../backend/app/api/routes_users.py), the provider
interface takes `query`, `limit` and `recent_first` and nothing else, and there is no
way to ask for the second page. On a directory with 8,000 enabled accounts, the
dashboard and the clone template picker both show an arbitrary 500 and give the
operator no signal that the rest exist.

## Why the audit-log pattern does not transfer

`GET /api/logs` already paginates properly — `limit` + `offset`, and a real `total`
from `SELECT COUNT(*)` alongside the page. The frontend
([`logs.ts`](../frontend/src/lib/pages/logs.ts)) turns that into
*showing 101–200 of 3,412* with working previous/next buttons.

That works because the audit store is SQLite: `OFFSET` is a supported operation and
`COUNT(*)` over the same `WHERE` clause is one extra cheap query. The user list is not
a table this application owns. It is a query against somebody else's directory, and
neither directory offers either primitive.

| | `OFFSET` equivalent | Exact total |
|---|---|---|
| SQLite (audit) | `OFFSET ?` | `SELECT COUNT(*)` |
| Active Directory over LDAP | none — RFC 2696 paged results are a forward-only, server-side cookie | none without enumerating the whole result set |
| Microsoft Graph `/users` | none — `$skip` is not supported; you follow `@odata.nextLink`, which carries an opaque `$skiptoken` | `$count` is a separate request and needs `ConsistencyLevel: eventual` |

`Get-ADUser` makes the LDAP position of this concrete: it has `-ResultPageSize` and
`-ResultSetSize`, and no `-Skip`.
[`Get-Users.ps1`](../powershell/scripts/Get-Users.ps1) passes `limit` straight into
`-ResultSetSize`, which is a ceiling on the whole search, not a window into it.

So an `offset` parameter on this endpoint could only be honoured in one of two ways:

1. **Fetch and discard.** Ask the directory for `offset + limit` results and throw the
   first `offset` away. Page 20 costs twenty times page 1, every page re-runs the
   search, and a user created between two requests shifts every subsequent page by
   one. This is the option that looks like the audit logs and behaves nothing like it.
2. **Keep server-side state.** Hold the LDAP paged-results cookie or the Graph
   `$skiptoken` between requests. That is correct, and it is a cursor — at which point
   the parameter should say so rather than pretending to be an offset.

## Proposed contract

A forward cursor, opaque to the client, with the page size still clamped at 500:

```http
GET /api/users?query=smith&limit=50&cursor=eyJwIjoyLCJrIjoi…
```

```json
{
  "users": [ … ],
  "count": 50,
  "next_cursor": "eyJwIjozLCJrIjoi…",
  "total": null,
  "total_is_estimate": false
}
```

| Field | Meaning |
|---|---|
| `count` | Rows in *this* page. Unchanged from today. |
| `next_cursor` | Pass it back to get the next page. `null` means this is the last page — that is the only end-of-results signal, and it is authoritative. |
| `total` | Exact count when the provider can supply one cheaply, otherwise `null`. Never a number the backend inferred. |
| `total_is_estimate` | `true` only when `total` came from something approximate, so the UI can render *about 8,000* rather than *8,000*. |

Four rules that keep it honest:

- **`cursor` and `offset` are not both offered.** Shipping `offset` as an alias
  implemented by fetch-and-discard would make the expensive, subtly wrong option the
  one every client reaches for first.
- **A cursor is opaque and single-purpose.** Base64 of a small JSON blob is fine;
  its contents are the provider's business. It must encode the query it was issued
  for, so replaying a cursor against a changed `query` fails loudly with `422` rather
  than returning a page of something else.
- **`total: null` is a normal answer, not an error.** The dashboard has to read well
  without it. *Showing 51–100* is a perfectly good status line; it is
  *showing 51–100 of 0* that makes the tool look broken.
- **Cursors expire.** An LDAP paged-results cookie is tied to a connection and a
  server. An expired or unknown cursor returns `410 Gone`, and the client's response
  is to go back to page 1 — not to retry.

## What each provider does with it

**`MockProvider`** ([`mock_provider.py`](../backend/app/services/mock_provider.py))
holds the seeded tenant in a list, so it can supply an exact `total` and encode the
slice index in the cursor. It is also the only place the whole contract can be tested,
which makes it the reference implementation rather than the toy one. Its cursor should
still be opaque and still expire, or the tests will pass on behaviour the real
providers cannot deliver.

**`PowerShellProvider`** ([`ps_provider.py`](../backend/app/services/ps_provider.py))
is the awkward one. The JSON-over-stdin contract is one process per call — the
PowerShell script exits, and the LDAP connection holding the cookie exits with it.
Two ways out, and the choice belongs in #5 rather than in this document:

- Have `Get-Users.ps1` return the cookie as an opaque string and accept it back on the
  next call, re-binding and resuming. Whether AD honours a resumed cookie across
  connections is the thing to test in a lab first — [#3](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/3)
  is already the issue for validating the PowerShell layer against real AD.
- Or paginate on a stable sort key instead of a cookie — `whenCreated` plus
  `objectGUID` as a tie-breaker — and have the cursor carry the last row's key. This
  is ordinary keyset pagination, it survives one process per call, and it costs an
  indexed range filter in the LDAP query. It cannot express *jump to page 20*, which
  the proposed contract does not offer anyway.

Keyset pagination is the safer default, because it needs nothing from the directory
that a fresh connection cannot do.

## Consequences for the frontend

The previous/next pattern in `logs.ts` survives; the page-number arithmetic does not.

- **Next** is enabled when `next_cursor` is non-null, not when `offset + PAGE_SIZE < total`.
- **Previous** needs a client-side stack of the cursors already visited. There is no
  *previous cursor* in the contract and inventing one would double the work on the
  provider side for a button.
- Changing `query` or `recent` discards the cursor stack and starts again, exactly as
  `logs.ts` resets `offset` to 0 today.
- The status line reads *showing 51–100* when `total` is `null`, and
  *showing 51–100 of 8,000* when it is not. Both shapes need to exist from the first
  commit, or the `null` case will be discovered by an operator rather than a test.

## Checklist for #5

- [ ] `limit` + `cursor` on `GET /api/users`, `offset` deliberately not offered.
- [ ] `next_cursor`, `total` and `total_is_estimate` in the response; `total: null` covered by a test.
- [ ] `IdentityProvider.list_users` signature updated, both implementations following it.
- [ ] `MockProvider` as the reference implementation: opaque cursor, expiry, exact total.
- [ ] `PowerShellProvider` on keyset pagination unless a lab proves cookie resumption works.
- [ ] `410` on an expired cursor, `422` on a cursor replayed against a different query.
- [ ] Previous/next plus a cursor stack in the users and clone-search tables.
- [ ] [`API.md`](API.md) row for `GET /users` updated — it still documents `limit` only.
