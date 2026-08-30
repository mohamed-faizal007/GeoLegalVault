import { useState } from "react";

import GeofenceManagementPanel from "../components/admin/GeofenceManagementPanel";
import HealthPanel from "../components/admin/HealthPanel";
import UserManagementPanel from "../components/admin/UserManagementPanel";

const TABS = ["Users", "Geofences", "System Health"] as const;
type Tab = (typeof TABS)[number];

export default function AdminPanel() {
  const [tab, setTab] = useState<Tab>("Users");

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-slate-900">Admin Panel</h1>

      <div className="flex gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium ${
              tab === t
                ? "border-b-2 border-slate-900 text-slate-900"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Users" && <UserManagementPanel />}
      {tab === "Geofences" && <GeofenceManagementPanel />}
      {tab === "System Health" && <HealthPanel />}
    </div>
  );
}
