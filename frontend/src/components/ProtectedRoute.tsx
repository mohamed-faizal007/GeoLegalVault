import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../context/useAuth";
import { hasPermission, type Permission } from "../lib/permissions";
import Spinner from "./Spinner";

/**
 * Route guard: redirects to /login when not authenticated, and — if a
 * `permission` (or, for an any-of check, `permissions`) is given — to
 * /forbidden when the role has none of them. This mirrors the server's RBAC
 * matrix for navigation UX only; the server's own deny-by-default check on
 * each request is the real boundary regardless of what this component
 * decides.
 */
export default function ProtectedRoute({
  children,
  permission,
  permissions,
}: {
  children: ReactNode;
  permission?: Permission;
  permissions?: Permission[];
}) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner label="Restoring your session…" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  const required = permissions ?? (permission ? [permission] : []);
  if (required.length > 0 && !required.some((p) => hasPermission(user.role, p))) {
    return <Navigate to="/forbidden" replace />;
  }

  return <>{children}</>;
}
