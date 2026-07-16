/** Session bootstrap shared by every authenticated page. */

import { api, appUrl, setCsrfToken } from "./api";
import type { SessionInfo } from "./types";

let pending: Promise<SessionInfo> | null = null;

export function requireSession(): Promise<SessionInfo> {
  // Layout and page scripts both call this; share one in-flight request.
  pending ??= api.get<SessionInfo>("/api/auth/me").then((session) => {
    setCsrfToken(session.csrf_token); // needed when the API is cross-origin
    return session;
  }); // 401 redirects to /login
  return pending;
}

export function can(session: SessionInfo, permission: string): boolean {
  return session.permissions.includes(permission);
}

export async function logout(): Promise<void> {
  await api.post("/api/auth/logout");
  pending = null;
  location.href = appUrl("/login");
}
