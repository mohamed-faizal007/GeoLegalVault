import { ChevronDown, LogOut, Settings } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ROLE_LABELS, type Role } from "../lib/permissions";

interface UserMenuProps {
  identity: string;
  role: string | undefined;
  onLogout: () => void;
}

/** Avatar + identity + role as one control; Settings and Log out live in the
 * dropdown. Closes on outside click and Escape (returning focus to the trigger). */
export default function UserMenu({ identity, role, onLogout }: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const roleLabel = role ? (ROLE_LABELS[role as Role] ?? role) : "";

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((v) => !v)}
        className={`group flex items-center gap-3 rounded-xl border px-2.5 py-1.5 text-left transition duration-200 ${
          open
            ? "border-brand-400/50 bg-white/10 shadow-card-hover"
            : "border-white/10 bg-white/5 hover:border-brand-400/40 hover:bg-white/10"
        }`}
      >
        <span
          aria-hidden="true"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-semibold text-white shadow-glow"
        >
          {identity.charAt(0).toUpperCase()}
        </span>
        <span className="hidden min-w-0 flex-col leading-tight sm:flex">
          <span className="max-w-[12rem] truncate text-sm font-medium text-ink">{identity}</span>
          <span className="text-xs font-medium text-brand-300">{roleLabel}</span>
        </span>
        <ChevronDown
          size={16}
          aria-hidden="true"
          className={`shrink-0 text-faint transition-transform duration-200 group-hover:text-muted ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open && (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 z-20 mt-2 w-56 animate-fade-in overflow-hidden rounded-xl border border-white/10 bg-raised p-1 shadow-[0_16px_40px_-12px_rgb(0_0_0_/_0.6)]"
        >
          <div className="border-b border-white/10 px-3 py-2 sm:hidden">
            <p className="truncate text-sm font-medium text-ink">{identity}</p>
            <p className="text-xs text-brand-300">{roleLabel}</p>
          </div>
          <Link
            role="menuitem"
            to="/settings"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-ink/90 transition-colors duration-150 hover:bg-white/10 hover:text-ink"
          >
            <Settings size={16} aria-hidden="true" className="text-faint" />
            Settings
          </Link>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-red-300 transition-colors duration-150 hover:bg-red-500/10"
          >
            <LogOut size={16} aria-hidden="true" />
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
