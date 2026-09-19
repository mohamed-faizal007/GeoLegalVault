import { useState } from "react";

import GeofenceManagementPanel from "../components/admin/GeofenceManagementPanel";
import HealthPanel from "../components/admin/HealthPanel";
import ReportsPanel from "../components/admin/ReportsPanel";
import UserManagementPanel from "../components/admin/UserManagementPanel";

const TABS = ["Users", "Geofences", "Reports", "System Health"] as const;
type Tab = (typeof TABS)[number];

export default function AdminPanel() {
  const [tab, setTab] = useState<Tab>("Users");

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-ink">Admin Panel</h1>

      <div className="flex gap-1 border-b border-white/10">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`-mb-px px-4 py-2 text-sm font-medium transition-colors ${
              tab === t
                ? "border-b-2 border-brand-600 text-brand-300"
                : "border-b-2 border-transparent text-muted hover:text-ink/90"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Users" && <UserManagementPanel />}
      {tab === "Geofences" && <GeofenceManagementPanel />}
      {tab === "Reports" && <ReportsPanel />}
      {tab === "System Health" && <HealthPanel />}
    </div>
  );
}
