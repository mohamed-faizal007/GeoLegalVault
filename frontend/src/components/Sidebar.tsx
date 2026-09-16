import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuth } from "../context/useAuth";
import { hasPermission, PERMISSIONS, type Permission } from "../lib/permissions";

interface NavItem {
  to: string;
  label: string;
  permission?: Permission;
  icon: ReactNode;
}

function icon(path: string): ReactNode {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4.5 w-4.5 shrink-0"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: icon("M3 10.5 12 3l9 7.5M5 9.5V21h14V9.5") },
  {
    to: "/documents",
    label: "Document Repository",
    icon: icon("M4 4h9l4 4v12H4V4Zm9 0v4h4M8 12h8M8 16h8M8 8h3"),
  },
  {
    to: "/documents/upload",
    label: "Upload",
    permission: PERMISSIONS.DOCUMENT_UPLOAD,
    icon: icon("M12 16V4m0 0 4 4m-4-4-4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"),
  },
  {
    to: "/geofence-status",
    label: "Geofence Status",
    icon: icon("M12 21s7-6.1 7-11.5A7 7 0 0 0 5 9.5C5 14.9 12 21 12 21Zm0-9a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z"),
  },
  {
    to: "/audit",
    label: "Audit Logs",
    permission: PERMISSIONS.AUDIT_VIEW,
    icon: icon("M9 4h10v14l-4-2-4 2V4Zm0 0H6a1 1 0 0 0-1 1v14l4-2 3 1.6"),
  },
  {
    to: "/admin",
    label: "Admin Panel",
    permission: PERMISSIONS.USERS_MANAGE,
    icon: icon("M12 3 4 6v6c0 5 3.4 7.7 8 9 4.6-1.3 8-4 8-9V6l-8-3Zm-2.5 9 2 2 3.5-3.5"),
  },
  {
    to: "/settings",
    label: "Settings",
    icon: icon(
      "M10.3 3h3.4l.5 2.4a7 7 0 0 1 1.8 1l2.3-.8 1.7 3-1.8 1.6a7 7 0 0 1 0 2l1.8 1.6-1.7 3-2.3-.8a7 7 0 0 1-1.8 1L13.7 21h-3.4l-.5-2.4a7 7 0 0 1-1.8-1l-2.3.8-1.7-3 1.8-1.6a7 7 0 0 1 0-2L4 10.2l1.7-3 2.3.8a7 7 0 0 1 1.8-1L10.3 3ZM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    ),
  },
];

export default function Sidebar() {
  const { user } = useAuth();

  return (
    <nav className="flex h-full w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center gap-2 px-4 py-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-600 text-sm font-bold text-white">
          G
        </span>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-slate-900">GeoLegalVault</p>
          <p className="text-[11px] text-slate-400">Document integrity vault</p>
        </div>
      </div>

      <div className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4">
        {NAV_ITEMS.filter((item) => !item.permission || hasPermission(user?.role, item.permission)).map(
          (item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `group flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span className={isActive ? "text-brand-600" : "text-slate-400 group-hover:text-slate-500"}>
                    {item.icon}
                  </span>
                  {item.label}
                </>
              )}
            </NavLink>
          ),
        )}
      </div>
    </nav>
  );
}
