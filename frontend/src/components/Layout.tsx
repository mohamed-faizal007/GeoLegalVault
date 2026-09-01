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
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <div>
            {user && (
              <span className="rounded-full bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white">
                {ROLE_LABELS[user.role as Role] ?? user.role}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <span>{user?.email || user?.id}</span>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100"
            >
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
