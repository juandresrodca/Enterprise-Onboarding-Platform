# The GitHub Pages demo bounces me back to the login screen

You signed in to the [live demo](https://juandresrodca.github.io/Enterprise-Onboarding-Platform/),
the credentials were accepted, and the app immediately returned you to the login
page. Nothing is broken on the server. The session cookie was set and then
discarded by your browser, because in that deployment it is a **third-party
cookie** — and this page explains which browsers drop it, what to do about it as
a visitor, and what the three possible fixes cost as a maintainer.

If you are reading this because the demo wasted five minutes of your time:
sorry. Skip to [As a visitor](#as-a-visitor).

## Why the deployment has this problem at all

The demo is split across two origins, because both halves are free:

```
https://juandresrodca.github.io   Astro frontend  (GitHub Pages)
https://<service>.onrender.com    FastAPI backend (Render, demo mode)
```

`POST /api/auth/login` answers with `Set-Cookie: eio_session=…; SameSite=None;
Secure`, and the frontend sends every subsequent request with
`credentials: "include"` (`frontend/src/lib/api.ts`). From the browser's point of
view the cookie belongs to `onrender.com` while the page in the address bar is
`github.io`, so it is a cross-site cookie and subject to whatever cross-site
cookie policy that browser enforces. When the policy is *drop it*, the next
request arrives unauthenticated, `get_current_user` rejects it, and the frontend
does the only sensible thing with a 401: it sends you back to the login screen.

Note what is **not** the cause. The password was right, the CSRF double-submit
is fine (the token is mirrored into the login response body precisely so a
cross-site frontend can read it), and Render's cold start — 30 to 60 seconds on
the free tier — makes the first request slow, not unauthenticated.

## Which browsers drop it

Measured against browser defaults as of **September 2026**. This table is the
part most likely to age, so it carries a date.

| Browser | Cross-site cookie default | The demo login |
|---|---|---|
| Chrome, normal window | **Allowed.** Google abandoned the phase-out on 22 April 2025 and dropped the standalone choice prompt with it. | Works |
| Chrome, Incognito | **Blocked.** Incognito enables Tracking Protection regardless of the main setting. | Fails |
| Chrome, cookies blocked by hand or by enterprise policy | Blocked | Fails |
| Edge | Allowed (tracker blocking is not a blanket third-party cookie block) | Works |
| Firefox | **Partitioned**, not blocked — Total Cookie Protection gives the cookie a jar keyed to the top-level site, and the top-level site is always the same one here | Works |
| Safari | **Blocked** by Intelligent Tracking Prevention, since 2020 | Fails |

So the honest summary is narrower than the one in
[issue #1](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/1),
which was written when Chrome's deprecation still looked inevitable: the demo
fails on Safari, in Chrome Incognito, and for anyone who has turned third-party
cookies off — not in Chrome by default. It is worth fixing anyway. "Works unless
you opened it in a private window" is not a demo you can put in a job
application, and a reader who hits it has no way to tell a cookie policy from a
broken login.

## As a visitor

Any one of these gets you in, in descending order of convenience:

1. **Use a normal window in Chrome, Edge or Firefox.** Incognito and private
   windows are the common failure.
2. **Allow third-party cookies for the API origin only.** In Chrome:
   *Settings → Privacy and security → Third-party cookies → Allowed sites →
   Add* with `[*.]onrender.com`. This is narrower than the global toggle, and
   narrower than what the README used to suggest.
3. **Run it locally instead**, where frontend and API share an origin and none of
   this applies:
   ```bash
   docker compose up            # http://localhost:8080
   ```
   The demo tenant, the demo accounts and the seeded data are identical.

Safari has no option 2 that survives ITP. Use option 1 or 3.

## As a maintainer: the three fixes, and what each one buys

### 1. Partition the cookie (CHIPS) — one line, fixes most of it

Adding the `Partitioned` attribute opts the cookie into partitioned storage: a
separate jar per top-level site, usable in a third-party context even where
unpartitioned third-party cookies are blocked. In `_set_session_cookies`
(`backend/app/api/routes_auth.py`) both `set_cookie` calls would take
`partitioned=(samesite == "none")`.

The attribute requires `Secure`, `Path=/` and no `Domain` — which is already
exactly how these two cookies are set — and Starlette exposes it as a
`set_cookie` keyword from 0.42 onwards, well inside the `fastapi>=0.115,<1.0`
pin in `requirements.txt`.

What it buys: Chrome Incognito, Chrome with third-party cookies blocked, and
Safari from 18.4, which added `Partitioned` support in April 2025. What it does
not buy: any browser where the user has blocked cookies outright, and Safari
where ITP has already classified the API host — ITP overrides the attribute.
Partitioning also means the session is scoped to the top-level site, which for
this deployment is the behaviour you want anyway.

### 2. Bearer-token mode — the actual fix, and what #1 proposes

Return the session JWT in the `login` and `me` response bodies when
`EIO_CROSS_SITE_AUTH=true`, keep it in `sessionStorage`, and send it as an
`Authorization` header. The backend already validates JWTs; only the transport
changes, and CSRF checks can be skipped for token auth because the token is not
ambient. This is the only option that survives a browser with cookies switched
off, and it is the one issue #1 is open for.

It is also the one with a security trade-off worth stating plainly: a token in
`sessionStorage` is readable by any script on the page, where the `httpOnly`
cookie is not. That is an acceptable trade for a demo tenant full of fictional
people, and it is why this stays behind an environment flag rather than becoming
the default.

### 3. Host both halves on one origin — what production should do

`docs/DEPLOYMENT.md` already says it: keep the `/api` proxy same-origin with the
frontend and the session cookie never needs third-party settings at all. The
`docker/` nginx configuration does this, and any real deployment of this platform
should. The split-origin demo exists because GitHub Pages and Render are free,
not because it is a good topology.

## Related

- [issue #1](https://github.com/juandresrodca/Enterprise-Onboarding-Platform/issues/1) — the open issue tracking fix 2
- [docs/DEPLOYMENT.md](DEPLOYMENT.md) — the GitHub Pages + Render recipe, and the same-origin production topology
- [SECURITY.md](../SECURITY.md) — the demo defaults that must change before this touches a real directory

Sources for the browser behaviour above, all checked on 22 September 2026:
Google's announcement of
[22 April 2025](https://privacysandbox.google.com/blog/privacy-sandbox-next-steps)
that it "will not be rolling out a new standalone prompt for third-party
cookies" and keeps the existing setting; MDN on
[third-party cookies](https://developer.mozilla.org/en-US/docs/Web/Privacy/Guides/Third-party_cookies),
which states that Chrome "doesn't block third-party cookies by default, only in
Incognito mode, or when users explicitly set it to block third-party cookies";
and [cookiestatus.com](https://www.cookiestatus.com/safari/) for Safari 18.4
adding the `Partitioned` attribute and for the ITP override that limits it.
