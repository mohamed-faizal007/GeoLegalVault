import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState, type FormEvent } from "react";

import { listGeofences } from "../../api/geofences";
import { createUser, listUsers, updateUser, type UserOut } from "../../api/users";
import { useAuth } from "../../context/useAuth";
import { ROLES } from "../../lib/permissions";
import ErrorBanner from "../ErrorBanner";
import Spinner from "../Spinner";

const ROLE_OPTIONS = Object.values(ROLES);

interface FenceOption {
  id: string;
  name: string;
}

/** Inline editor for role / name / assigned geofences (PATCH /users/{id}). The
 * server also refuses an admin demoting themselves; disabling the role select
 * on the admin's own row is only a courtesy so they don't hit that error. */
function UserEditForm({
  user,
  fences,
  isSelf,
  onDone,
}: {
  user: UserOut;
  fences: FenceOption[];
  isSelf: boolean;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(user.name);
  const [role, setRole] = useState<string>(user.role);
  const [fenceIds, setFenceIds] = useState<string[]>(user.assigned_geofence_ids);

  const mutation = useMutation({
    mutationFn: () => updateUser(user.id, { name, role, assigned_geofence_ids: fenceIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      onDone();
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 bg-raised/40 p-4">
      <div className="grid grid-cols-2 gap-3">
        <input
          required
          aria-label="Full name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="input"
        />
        <select
          aria-label="Role"
          value={role}
          disabled={isSelf}
          onChange={(e) => setRole(e.target.value)}
          className="input"
        >
          {ROLE_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </div>
      {isSelf && (
        <p className="text-xs text-faint">You can't change your own role or deactivate yourself.</p>
      )}
      <div>
        <p className="mb-1 text-xs font-medium text-muted">
          Assigned geofences (hold Ctrl/Cmd to select several)
        </p>
        <select
          multiple
          aria-label="Assigned geofences"
          value={fenceIds}
          onChange={(e) => setFenceIds(Array.from(e.target.selectedOptions, (o) => o.value))}
          className="input"
        >
          {fences.map((fence) => (
            <option key={fence.id} value={fence.id}>
              {fence.name}
            </option>
          ))}
        </select>
      </div>
      {mutation.error && <ErrorBanner error={mutation.error} />}
      <div className="flex gap-2">
        <button type="submit" disabled={mutation.isPending} className="btn-primary btn-sm">
          {mutation.isPending ? "Saving…" : "Save changes"}
        </button>
        <button type="button" onClick={onDone} className="btn-secondary btn-sm">
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function UserManagementPanel() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  const [editingId, setEditingId] = useState<string | null>(null);
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

  const fenceOptions: FenceOption[] = geofencesQuery.data?.items ?? [];
  const fenceNames = new Map(fenceOptions.map((f) => [f.id, f.name]));

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
            {fenceOptions.map((fence) => (
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

      {toggleActiveMutation.error && <ErrorBanner error={toggleActiveMutation.error} />}

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
                <th className="px-4 py-2.5 font-medium">Geofences</th>
                <th className="px-4 py-2.5 font-medium">Active</th>
                <th className="px-4 py-2.5 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {usersQuery.data.items.map((u) => {
                const isSelf = u.id === currentUser?.id;
                return (
                  <Fragment key={u.id}>
                    <tr className="table-row-hover">
                      <td className="px-4 py-2.5">{u.email}</td>
                      <td className="px-4 py-2.5">{u.name}</td>
                      <td className="px-4 py-2.5 text-muted">{u.role}</td>
                      <td className="px-4 py-2.5">
                        {u.assigned_geofence_ids.length === 0 ? (
                          <span
                            title="Upload, download, approve and amend are denied without an assigned geofence"
                            className="inline-flex items-center rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-300 ring-1 ring-inset ring-amber-400/30"
                          >
                            No geofence
                          </span>
                        ) : (
                          <span className="text-xs text-muted">
                            {u.assigned_geofence_ids
                              .map((id) => fenceNames.get(id) ?? "Unknown fence")
                              .join(", ")}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        {u.is_active ? (
                          <span className="text-emerald-300">Active</span>
                        ) : (
                          <span className="text-faint">Deactivated</span>
                        )}
                      </td>
                      <td className="space-x-3 px-4 py-2.5 text-right">
                        <button
                          type="button"
                          onClick={() => setEditingId(editingId === u.id ? null : u.id)}
                          className="text-xs font-medium text-brand-400 underline hover:text-brand-300"
                        >
                          {editingId === u.id ? "Close" : "Edit"}
                        </button>
                        <button
                          type="button"
                          disabled={isSelf && u.is_active}
                          title={isSelf ? "You can't deactivate your own account" : undefined}
                          onClick={() =>
                            toggleActiveMutation.mutate({ id: u.id, isActive: u.is_active })
                          }
                          className="text-xs font-medium text-brand-400 underline hover:text-brand-300 disabled:cursor-not-allowed disabled:opacity-40 disabled:no-underline"
                        >
                          {u.is_active ? "Deactivate" : "Reactivate"}
                        </button>
                      </td>
                    </tr>
                    {editingId === u.id && (
                      <tr>
                        <td colSpan={6} className="p-0">
                          <UserEditForm
                            user={u}
                            fences={fenceOptions}
                            isSelf={isSelf}
                            onDone={() => setEditingId(null)}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
