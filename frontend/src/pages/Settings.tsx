import { useState, type FormEvent } from "react";

import { useAuth } from "../context/AuthContext";
import { ROLE_LABELS, type Role } from "../lib/permissions";

export default function Settings() {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (newPassword.length < 8) {
      setValidationError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setValidationError("New password and confirmation don't match.");
      return;
    }
    setValidationError(null);
  }

  return (
    <div className="max-w-md space-y-6">
      <h1 className="text-lg font-semibold text-slate-900">Settings</h1>

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">Profile</h2>
        <dl className="mt-2 space-y-1 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-400">Email</dt>
            <dd className="text-slate-700">{user?.email || "—"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-400">Role</dt>
            <dd className="text-slate-700">{user ? ROLE_LABELS[user.role as Role] ?? user.role : "—"}</dd>
          </div>
        </dl>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
      >
        <h2 className="text-sm font-semibold text-slate-800">Change password</h2>

        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Self-service password change isn't available in this backend version yet — ask an
          Administrator to reset your password. This form validates your input, but submitting it
          won't reach the server.
        </div>

        <input
          type="password"
          placeholder="Current password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          autoComplete="current-password"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <input
          type="password"
          placeholder="New password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          autoComplete="new-password"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <input
          type="password"
          placeholder="Confirm new password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          autoComplete="new-password"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />

        {validationError && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{validationError}</p>
        )}

        <button
          type="submit"
          disabled={!currentPassword || !newPassword || !confirmPassword}
          className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          Save (not yet wired to a backend endpoint)
        </button>
      </form>
    </div>
  );
}
