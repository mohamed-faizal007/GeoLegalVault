import { useEffect, useState, type ReactNode } from "react";

import * as authApi from "../api/auth";
import { getMe } from "../api/users";
import {
  configureOnUnauthorized,
  configureRefresh,
  getAccessToken,
  setSession,
  type StoredUser,
} from "../lib/authToken";
import { decodeAccessToken } from "../lib/jwt";
import { AuthContext } from "./useAuth";

const EMAIL_KEY_PREFIX = "geolegalvault:lastEmail:";

function rememberEmail(userId: string, email: string): void {
  try {
    sessionStorage.setItem(EMAIL_KEY_PREFIX + userId, email);
  } catch {
    // sessionStorage unavailable (private mode, etc.) — non-critical, UI just
    // falls back to showing the account id instead of the email.
  }
}

function recallEmail(userId: string): string {
  try {
    return sessionStorage.getItem(EMAIL_KEY_PREFIX + userId) ?? "";
  } catch {
    return "";
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<StoredUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  /** Fill in name and email from GET /users/me. Best effort: the UI falls back to the email, then
   * the id, so a failure here never blocks sign-in. Skipped if the session changed meanwhile. */
  function loadProfile(base: StoredUser): void {
    getMe()
      .then((me) => {
        const token = getAccessToken();
        if (!token) return;
        const enriched: StoredUser = { ...base, name: me.name, email: me.email };
        setSession(token, enriched);
        setUser((current) => (current?.id === base.id ? enriched : current));
      })
      .catch(() => undefined);
  }

  useEffect(() => {
    async function doRefresh(): Promise<string> {
      const res = await authApi.refresh();
      const claims = decodeAccessToken(res.access_token);
      const nextUser: StoredUser | null = claims
        ? { id: claims.sub, role: claims.role, email: recallEmail(claims.sub) }
        : null;
      setSession(res.access_token, nextUser);
      setUser(nextUser);
      if (nextUser) loadProfile(nextUser);
      return res.access_token;
    }

    configureRefresh(doRefresh);
    configureOnUnauthorized(() => {
      setSession(null, null);
      setUser(null);
    });

    // Silent session restore on load: relies on the httpOnly refresh cookie.
    // Expected to fail (and simply show the login page) whenever that cookie
    // isn't present — e.g. first visit, or a cleared/expired session.
    doRefresh()
      .catch(() => {
        setSession(null, null);
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function login(email: string, password: string): Promise<void> {
    const res = await authApi.login(email, password);
    const claims = decodeAccessToken(res.access_token);
    if (!claims) throw new Error("Received an unreadable access token");
    const nextUser: StoredUser = { id: claims.sub, role: claims.role, email };
    rememberEmail(claims.sub, email);
    setSession(res.access_token, nextUser);
    setUser(nextUser);
    loadProfile(nextUser);
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout();
    } catch {
      // best-effort: clear local session regardless of whether the server
      // call succeeded (e.g. the access token was already expired)
    }
    setSession(null, null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
