import { useMemo, useState } from "react";

import GeofenceManagementPanel from "../components/admin/GeofenceManagementPanel";
import HealthPanel from "../components/admin/HealthPanel";
import ReportsPanel from "../components/admin/ReportsPanel";
import UserManagementPanel from "../components/admin/UserManagementPanel";
import { useAuth } from "../context/useAuth";
import { hasPermission, PERMISSIONS, type Permission } from "../lib/permissions";

const TABS = ["Users", "Geofences", "Reports", "System Health"] as const;
type Tab = (typeof TABS)[number];

// Each tab mirrors the one server-side permission that actually backs it —
// the route itself only requires *any* admin-tab permission (see App.tsx),
// so a role like Auditor (AUDIT_VIEW only) lands here with just Reports
// visible instead of being bounced to /forbidden.
const TAB_PERMISSION: Record<Tab, Permission> = {
  Users: PERMISSIONS.USERS_MANAGE,
  Geofences: PERMISSIONS.GEOFENCE_MANAGE,
  Reports: PERMISSIONS.AUDIT_VIEW,
  "System Health": PERMISSIONS.USERS_MANAGE,
};

export default function AdminPanel() {
  const { user } = useAuth();
  const visibleTabs = useMemo(
    () => TABS.filter((t) => hasPermission(user?.role, TAB_PERMISSION[t])),
    [user?.role],
  );
  const [tab, setTab] = useState<Tab>(visibleTabs[0] ?? "Reports");
  const activeTab = visibleTabs.includes(tab) ? tab : visibleTabs[0];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-ink">Admin Panel</h1>

      <div className="flex gap-1 border-b border-white/10">
        {visibleTabs.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`-mb-px px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === t
                ? "border-b-2 border-brand-600 text-brand-300"
                : "border-b-2 border-transparent text-muted hover:text-ink/90"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {activeTab === "Users" && <UserManagementPanel />}
      {activeTab === "Geofences" && <GeofenceManagementPanel />}
      {activeTab === "Reports" && <ReportsPanel />}
      {activeTab === "System Health" && <HealthPanel />}
    </div>
  );
}
