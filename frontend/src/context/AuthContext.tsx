import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import * as authApi from "../api/auth";
import { configureOnUnauthorized, configureRefresh, setSession, type StoredUser } from "../lib/authToken";
import { decodeAccessToken } from "../lib/jwt";

interface AuthContextValue {
  user: StoredUser | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

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

  useEffect(() => {
    async function doRefresh(): Promise<string> {
      const res = await authApi.refresh();
      const claims = decodeAccessToken(res.access_token);
      const nextUser: StoredUser | null = claims
        ? { id: claims.sub, role: claims.role, email: recallEmail(claims.sub) }
        : null;
      setSession(res.access_token, nextUser);
      setUser(nextUser);
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

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
