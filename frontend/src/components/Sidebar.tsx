import {
  FolderOpen,
  LayoutDashboard,
  MapPin,
  ScrollText,
  Settings,
  ShieldCheck,
  Upload,
  type LucideIcon,
} from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";

import { useAuth } from "../context/useAuth";
import { hasPermission, PERMISSIONS, type Permission } from "../lib/permissions";

interface NavItem {
  to: string;
  label: string;
  /** Any-of when more than one permission would unlock this link. */
  permission?: Permission;
  permissions?: Permission[];
  icon: LucideIcon;
  group: "Workspace" | "Manage";
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, group: "Workspace" },
  { to: "/documents", label: "Document Repository", icon: FolderOpen, group: "Workspace" },
  {
    to: "/documents/upload",
    label: "Upload",
    permission: PERMISSIONS.DOCUMENT_UPLOAD,
    icon: Upload,
    group: "Workspace",
  },
  { to: "/geofence-status", label: "Geofence Status", icon: MapPin, group: "Workspace" },
  {
    to: "/audit",
    label: "Audit Logs",
    permission: PERMISSIONS.AUDIT_VIEW,
    icon: ScrollText,
    group: "Manage",
  },
  {
    to: "/admin",
    label: "Admin Panel",
    permissions: [PERMISSIONS.USERS_MANAGE, PERMISSIONS.GEOFENCE_MANAGE, PERMISSIONS.AUDIT_VIEW],
    icon: ShieldCheck,
    group: "Manage",
  },
  { to: "/settings", label: "Settings", icon: Settings, group: "Manage" },
];

/** Visual-only: "/documents" prefix-matches "/documents/upload", which would
 * light two items at once. Routing itself is unchanged. */
function isItemActive(to: string, routeActive: boolean, pathname: string): boolean {
  if (to === "/documents" && pathname.startsWith("/documents/upload")) return false;
  return routeActive;
}

const GROUPS: NavItem["group"][] = ["Workspace", "Manage"];

export default function Sidebar() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const visible = NAV_ITEMS.filter((item) => {
    const required = item.permissions ?? (item.permission ? [item.permission] : []);
    return required.length === 0 || required.some((p) => hasPermission(user?.role, p));
  });

  return (
    <nav className="relative flex h-full w-64 shrink-0 flex-col border-r border-white/10 bg-surface">
      {/* Soft brand glow behind the logo — decorative only */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-[radial-gradient(ellipse_at_top_left,rgb(99_102_241_/_0.22),transparent_70%)]"
      />

      <div className="relative flex items-center gap-3 px-5 py-5">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-sm font-bold text-white shadow-glow">
          G
        </span>
        <div className="leading-tight">
          <p className="text-sm font-semibold tracking-tight text-ink">GeoLegalVault</p>
          <p className="text-[11px] text-faint">Document integrity vault</p>
        </div>
      </div>

      <div className="relative flex-1 space-y-6 overflow-y-auto px-3 pb-4 pt-2">
        {GROUPS.map((group) => {
          const items = visible.filter((item) => item.group === group);
          if (items.length === 0) return null;
          return (
            <div key={group}>
              <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wider text-faint">
                {group}
              </p>
              <div className="space-y-1">
                {items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.to === "/"}
                      className={({ isActive: routeActive }) => {
                        const isActive = isItemActive(item.to, routeActive, pathname);
                        return `group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200 ${
                          isActive
                            ? "bg-gradient-to-r from-brand-500/20 to-brand-500/0 text-ink shadow-[inset_0_0_0_1px_rgb(129_140_248_/_0.22)]"
                            : "text-muted hover:bg-white/5 hover:text-ink"
                        }`;
                      }}
                    >
                      {({ isActive: routeActive }) => {
                        const isActive = isItemActive(item.to, routeActive, pathname);
                        return (
                        <>
                          {isActive && (
                            <span
                              aria-hidden="true"
                              className="absolute -left-3 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brand-400 shadow-[0_0_12px_2px_rgb(129_140_248_/_0.7)]"
                            />
                          )}
                          <Icon
                            size={18}
                            strokeWidth={1.75}
                            aria-hidden="true"
                            className={`shrink-0 transition-colors duration-200 ${
                              isActive
                                ? "text-brand-300 drop-shadow-[0_0_6px_rgb(129_140_248_/_0.8)]"
                                : "text-faint group-hover:text-muted"
                            }`}
                          />
                          {item.label}
                        </>
                        );
                      }}
                    </NavLink>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      <p className="relative border-t border-white/10 px-5 py-3 text-[11px] text-faint">
        Prototype build · Sepolia testnet
      </p>
    </nav>
  );
}
