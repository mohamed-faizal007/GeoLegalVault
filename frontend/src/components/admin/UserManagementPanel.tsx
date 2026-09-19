import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { listGeofences } from "../../api/geofences";
import { createUser, listUsers, updateUser } from "../../api/users";
import { ROLES } from "../../lib/permissions";
import ErrorBanner from "../ErrorBanner";
import Spinner from "../Spinner";

const ROLE_OPTIONS = Object.values(ROLES);

export default function UserManagementPanel() {
  const queryClient = useQueryClient();
  const usersQuery = useQuery({ queryKey: ["admin", "users"], queryFn: () => listUsers(1, 100) });
  const geofencesQuery = useQuery({
    queryKey: ["admin", "geofences-for-users"],
    queryFn: () => listGeofences(1, 100),
  });

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<string>(ROLES.AUTHORIZED_STAFF);
  const [fenceIds, setFenceIds] = useState<string[]>([]);

  const createMutation = useMutation({
    mutationFn: () =>
      createUser({ email, password, name, role, assigned_geofence_ids: fenceIds }),
    onSuccess: () => {
      setEmail("");
      setPassword("");
      setName("");
      setFenceIds([]);
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      updateUser(id, { is_active: !isActive }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  function handleCreate(e: FormEvent) {
    e.preventDefault();
    createMutation.mutate();
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleCreate} className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold text-ink">Create user</h2>
        <div className="grid grid-cols-2 gap-3">
          <input
            required
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input"
          />
          <input
            required
            type="password"
            placeholder="Temporary password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            className="input"
          />
          <input
            required
            placeholder="Full name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="input"
          />
          <select value={role} onChange={(e) => setRole(e.target.value)} className="input">
            {ROLE_OPTIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-muted">Assigned geofences</p>
          <select
            multiple
            value={fenceIds}
            onChange={(e) => setFenceIds(Array.from(e.target.selectedOptions, (o) => o.value))}
            className="input"
          >
            {geofencesQuery.data?.items.map((fence) => (
              <option key={fence.id} value={fence.id}>
                {fence.name}
              </option>
            ))}
          </select>
        </div>
        {createMutation.error && <ErrorBanner error={createMutation.error} />}
        <button type="submit" disabled={createMutation.isPending} className="btn-primary">
          {createMutation.isPending ? "Creating…" : "Create user"}
        </button>
      </form>

      <div className="card overflow-hidden">
        {usersQuery.isLoading && <Spinner label="Loading users…" />}
        {usersQuery.error && (
          <div className="p-4">
            <ErrorBanner error={usersQuery.error} />
          </div>
        )}
        {usersQuery.data && (
          <table className="w-full text-left text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-4 py-2.5 font-medium">Email</th>
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Role</th>
                <th className="px-4 py-2.5 font-medium">Active</th>
                <th className="px-4 py-2.5 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {usersQuery.data.items.map((u) => (
                <tr key={u.id} className="table-row-hover">
                  <td className="px-4 py-2.5">{u.email}</td>
                  <td className="px-4 py-2.5">{u.name}</td>
                  <td className="px-4 py-2.5 text-muted">{u.role}</td>
                  <td className="px-4 py-2.5">
                    {u.is_active ? (
                      <span className="text-emerald-300">Active</span>
                    ) : (
                      <span className="text-faint">Deactivated</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      type="button"
                      onClick={() => toggleActiveMutation.mutate({ id: u.id, isActive: u.is_active })}
                      className="text-xs font-medium text-brand-400 underline hover:text-brand-300"
                    >
                      {u.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
