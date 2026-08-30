/**
 * The access token lives only in memory (never localStorage/sessionStorage —
 * Plan Part 16: "Access token in memory; refresh via httpOnly cookie").
 * This module is a plain singleton (not React state) so the low-level API
 * client (api/http.ts) can read the current token and react to 401s without
 * importing AuthContext — AuthContext is the only writer, wiring itself in
 * via `configureAuthToken` once at startup.
 */

export interface StoredUser {
  id: string;
  role: string;
  email: string;
}

let accessToken: string | null = null;
let currentUser: StoredUser | null = null;

let refreshFn: (() => Promise<string>) | null = null;
let onUnauthorizedFn: (() => void) | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function getCurrentUser(): StoredUser | null {
  return currentUser;
}

export function setSession(token: string | null, user: StoredUser | null): void {
  accessToken = token;
  currentUser = user;
}

/** Wired by AuthContext: how to obtain a fresh access token (POST /auth/refresh). */
export function configureRefresh(fn: () => Promise<string>): void {
  refreshFn = fn;
}

/** Wired by AuthContext: what to do when refresh also fails (clear session, go to /login). */
export function configureOnUnauthorized(fn: () => void): void {
  onUnauthorizedFn = fn;
}

export async function tryRefresh(): Promise<string | null> {
  if (!refreshFn) return null;
  try {
    return await refreshFn();
  } catch {
    return null;
  }
}

export function notifyUnauthorized(): void {
  onUnauthorizedFn?.();
}
