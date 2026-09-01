import { NavLink } from "react-router-dom";

import { useAuth } from "../context/useAuth";
import { hasPermission, PERMISSIONS, type Permission } from "../lib/permissions";

interface NavItem {
  to: string;
  label: string;
  permission?: Permission;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard" },
  { to: "/documents", label: "Document Repository" },
  { to: "/documents/upload", label: "Upload", permission: PERMISSIONS.DOCUMENT_UPLOAD },
  { to: "/geofence-status", label: "Geofence Status" },
  { to: "/audit", label: "Audit Logs", permission: PERMISSIONS.AUDIT_VIEW },
  { to: "/admin", label: "Admin Panel", permission: PERMISSIONS.USERS_MANAGE },
  { to: "/settings", label: "Settings" },
];

export default function Sidebar() {
  const { user } = useAuth();

  return (
    <nav className="flex h-full w-56 shrink-0 flex-col gap-1 border-r border-slate-200 bg-white px-3 py-4">
      <p className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
        GeoLegalVault
      </p>
      {NAV_ITEMS.filter((item) => !item.permission || hasPermission(user?.role, item.permission)).map(
        (item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
              }`
            }
          >
            {item.label}
          </NavLink>
        ),
      )}
    </nav>
  );
}
