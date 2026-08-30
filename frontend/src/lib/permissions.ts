/**
 * Client-side mirror of backend/app/core/rbac.py's ROLE_PERMISSIONS (Plan
 * Part 3, exact matrix). This is UX ONLY — it hides sidebar links and
 * disables buttons a user's role could never use, so they aren't led into a
 * dead end. It is never the security boundary: every one of these
 * permissions is re-checked server-side (deny-by-default), and the server
 * decision is authoritative regardless of what this file says.
 */

export const PERMISSIONS = {
  DOCUMENT_UPLOAD: "document:upload",
  DOCUMENT_VIEW: "document:view",
  DOCUMENT_SEARCH: "document:search",
  DOCUMENT_SUBMIT: "document:submit",
  DOCUMENT_AMEND: "document:amend",
  DOCUMENT_ARCHIVE: "document:archive",
  REVIEW_PERFORM: "review:perform",
  APPROVE_PERFORM: "approve:perform",
  VERIFY_PERFORM: "verify:perform",
  USERS_MANAGE: "users:manage",
  GEOFENCE_MANAGE: "geofence:manage",
  AUDIT_VIEW: "audit:view",
} as const;

export type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

export const ROLES = {
  ADMINISTRATOR: "ADMINISTRATOR",
  LEGAL_OFFICER: "LEGAL_OFFICER",
  REVIEWING_OFFICER: "REVIEWING_OFFICER",
  AUTHORIZED_STAFF: "AUTHORIZED_STAFF",
  AUDITOR: "AUDITOR",
} as const;

export type Role = (typeof ROLES)[keyof typeof ROLES];

const ROLE_PERMISSIONS: Record<Role, Set<Permission>> = {
  ADMINISTRATOR: new Set([
    PERMISSIONS.DOCUMENT_VIEW,
    PERMISSIONS.DOCUMENT_SEARCH,
    PERMISSIONS.VERIFY_PERFORM,
    PERMISSIONS.USERS_MANAGE,
    PERMISSIONS.GEOFENCE_MANAGE,
    PERMISSIONS.AUDIT_VIEW,
    PERMISSIONS.DOCUMENT_ARCHIVE,
  ]),
  LEGAL_OFFICER: new Set([
    PERMISSIONS.DOCUMENT_UPLOAD,
    PERMISSIONS.DOCUMENT_VIEW,
    PERMISSIONS.DOCUMENT_SEARCH,
    PERMISSIONS.DOCUMENT_SUBMIT,
    PERMISSIONS.DOCUMENT_AMEND,
    PERMISSIONS.DOCUMENT_ARCHIVE,
    PERMISSIONS.APPROVE_PERFORM,
    PERMISSIONS.VERIFY_PERFORM,
  ]),
  REVIEWING_OFFICER: new Set([
    PERMISSIONS.DOCUMENT_VIEW,
    PERMISSIONS.DOCUMENT_SEARCH,
    PERMISSIONS.REVIEW_PERFORM,
    PERMISSIONS.VERIFY_PERFORM,
  ]),
  AUTHORIZED_STAFF: new Set([
    PERMISSIONS.DOCUMENT_UPLOAD,
    PERMISSIONS.DOCUMENT_VIEW,
    PERMISSIONS.DOCUMENT_SEARCH,
    PERMISSIONS.DOCUMENT_SUBMIT,
    PERMISSIONS.DOCUMENT_AMEND,
    PERMISSIONS.VERIFY_PERFORM,
  ]),
  AUDITOR: new Set([
    PERMISSIONS.DOCUMENT_VIEW,
    PERMISSIONS.DOCUMENT_SEARCH,
    PERMISSIONS.VERIFY_PERFORM,
    PERMISSIONS.AUDIT_VIEW,
  ]),
};

export function hasPermission(role: string | undefined, permission: Permission): boolean {
  if (!role || !(role in ROLE_PERMISSIONS)) return false;
  return ROLE_PERMISSIONS[role as Role].has(permission);
}

export const ROLE_LABELS: Record<Role, string> = {
  ADMINISTRATOR: "Administrator",
  LEGAL_OFFICER: "Legal Officer",
  REVIEWING_OFFICER: "Reviewing Officer",
  AUTHORIZED_STAFF: "Authorized Staff",
  AUDITOR: "Auditor",
};
