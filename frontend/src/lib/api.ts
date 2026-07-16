/** Fetch wrapper: cookies, CSRF header, typed errors, 401 redirect.
 *
 * Deploy modes:
 *  - same-origin (dev proxy / nginx / docker): PUBLIC_API_BASE unset.
 *  - split hosting (e.g. GitHub Pages + Render API): set PUBLIC_API_BASE to
 *    the backend origin at build time; cookies switch to credentials:include
 *    and the CSRF token comes from the session body (the API origin's cookie
 *    is unreadable cross-site).
 */

const API_BASE = ((import.meta.env.PUBLIC_API_BASE as string | undefined) ?? "").replace(/\/+$/, "");

/** Prefix an /api/... path with the configured backend origin. */
export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

/** Prefix an app route with Astro's base path (GitHub Pages project sites). */
export function appUrl(path: string): string {
  const base = ((import.meta.env.BASE_URL as string) ?? "/").replace(/\/+$/, "");
  return `${base}${path}` || "/";
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail: unknown = null) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

let sessionCsrf = "";

/** Remember the CSRF token mirrored in login//me responses. */
export function setCsrfToken(token: string | null | undefined): void {
  if (token) sessionCsrf = token;
}

function csrfToken(): string {
  if (sessionCsrf) return sessionCsrf;
  const match = document.cookie.match(/(?:^|;\s*)eio_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options: { form?: FormData; redirectOn401?: boolean } = {},
): Promise<T> {
  const { form, redirectOn401 = true } = options;
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["X-CSRF-Token"] = csrfToken();
  if (body !== undefined && !form) headers["Content-Type"] = "application/json";

  const response = await fetch(apiUrl(path), {
    method,
    headers,
    credentials: API_BASE ? "include" : "same-origin",
    body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });

  if (response.status === 401 && redirectOn401 && !location.pathname.includes("/login")) {
    location.href = appUrl("/login");
    throw new ApiError(401, "Session expired");
  }

  const text = await response.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    const detail = (data as { detail?: unknown })?.detail ?? data;
    const message =
      typeof detail === "string"
        ? detail
        : ((detail as { message?: string })?.message ?? `Request failed (${response.status})`);
    throw new ApiError(response.status, message, detail);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  upload: <T>(path: string, form: FormData) => request<T>("POST", path, undefined, { form }),
  postNoRedirect: <T>(path: string, body?: unknown) =>
    request<T>("POST", path, body, { redirectOn401: false }),
};
