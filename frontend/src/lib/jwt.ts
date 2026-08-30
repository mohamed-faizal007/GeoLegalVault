/**
 * Decodes (never verifies — the server already verified it; we just read our
 * own token to learn `sub`/`role` for the UI) the payload of the JWT access
 * token returned by POST /auth/login. There's no `/users/me` endpoint (Phase
 * 1 only built admin-provisioned user management), so this is the only way
 * the frontend learns the current user's id and role.
 */
export interface AccessTokenClaims {
  sub: string;
  role: string;
  iat: number;
  exp: number;
  jti: string;
}

export function decodeAccessToken(token: string): AccessTokenClaims | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const json = decodeURIComponent(
      atob(padded)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join(""),
    );
    return JSON.parse(json) as AccessTokenClaims;
  } catch {
    return null;
  }
}
