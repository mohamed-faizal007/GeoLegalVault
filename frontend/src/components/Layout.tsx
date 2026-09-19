import { Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../context/useAuth";
import Sidebar from "./Sidebar";
import UserMenu from "./UserMenu";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex h-screen bg-canvas">
      <Sidebar />
      <div className="relative flex min-w-0 flex-1 flex-col">
        {/* Faint top glow for depth; decorative only */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-[radial-gradient(ellipse_at_top,rgb(99_102_241_/_0.12),transparent_70%)]"
        />
        <header className="relative z-10 flex items-center justify-end border-b border-white/10 bg-surface/80 px-6 py-3 backdrop-blur">
          {user && (
            <UserMenu
              identity={user.email || user.id}
              role={user.role}
              onLogout={handleLogout}
            />
          )}
        </header>
        <main className="relative min-w-0 flex-1 overflow-y-auto p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
