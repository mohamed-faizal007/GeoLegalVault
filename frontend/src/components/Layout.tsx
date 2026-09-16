import { Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../context/useAuth";
import { ROLE_LABELS, type Role } from "../lib/permissions";
import Sidebar from "./Sidebar";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3 shadow-sm">
          <div>
            {user && (
              <span className="inline-flex items-center rounded-full bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700 ring-1 ring-inset ring-brand-600/20">
                {ROLE_LABELS[user.role as Role] ?? user.role}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-600">
                {(user?.email || user?.id || "?").charAt(0).toUpperCase()}
              </span>
              <span className="max-w-[14rem] truncate">{user?.email || user?.id}</span>
            </div>
            <button type="button" onClick={handleLogout} className="btn-secondary btn-sm">
              Log out
            </button>
          </div>
        </header>
        <main className="min-w-0 flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
