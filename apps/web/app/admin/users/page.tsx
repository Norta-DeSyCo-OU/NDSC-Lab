"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { Alert } from "@/components/Alert";

type User = {
  id: string;
  email: string;
  role: "user" | "contributor" | "admin";
  state: string;
  display_name: string | null;
  created_at: string;
};

export default function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [state, setState] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setErr(null);
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (role) params.set("role", role);
      if (state) params.set("state", state);
      params.set("limit", "100");
      const data = await apiGet<User[]>(`/admin/users?${params.toString()}`);
      setUsers(data);
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function changeRole(u: User, newRole: User["role"]) {
    if (!confirm(`Change ${u.email} from ${u.role} to ${newRole}?`)) return;
    try {
      await apiPost(`/admin/users/${u.id}/role`, { role: newRole });
      await load();
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    }
  }

  async function ban(u: User) {
    const reason = prompt(`Reason for banning ${u.email}? (logged in audit)`);
    if (reason === null) return;
    try {
      await apiPost(`/admin/users/${u.id}/ban`, { reason });
      await load();
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3 justify-between">
        <h1 className="text-2xl font-bold">Users</h1>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
        className="flex flex-wrap gap-2 items-end"
        role="search"
      >
        <label className="flex-1 min-w-48">
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">Search email / name</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-full px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
          />
        </label>
        <label>
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">Role</span>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
          >
            <option value="">Any</option>
            <option value="user">User</option>
            <option value="contributor">Contributor</option>
            <option value="admin">Admin</option>
          </select>
        </label>
        <label>
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">State</span>
          <select
            value={state}
            onChange={(e) => setState(e.target.value)}
            className="px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
          >
            <option value="">Any</option>
            <option value="active">Active</option>
            <option value="pending_verify">Pending</option>
            <option value="banned">Banned</option>
            <option value="deleted">Deleted</option>
          </select>
        </label>
        <button
          type="submit"
          disabled={busy}
          className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium disabled:opacity-60"
        >
          {busy ? "…" : "Search"}
        </button>
      </form>

      {err && <Alert kind="error">{err}</Alert>}

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead className="text-[var(--color-fg-muted)] text-xs uppercase">
            <tr className="border-b border-[var(--color-brand-blue-4)]">
              <th className="text-left py-2 px-1">Email</th>
              <th className="text-left py-2 px-1">Role</th>
              <th className="text-left py-2 px-1">State</th>
              <th className="text-left py-2 px-1">Created</th>
              <th className="text-right py-2 px-1">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-[var(--color-brand-blue-4)]/50 hover:bg-[var(--color-brand-blue-4)]/10">
                <td className="py-2 px-1">
                  <div>{u.email}</div>
                  <div className="text-xs text-[var(--color-fg-muted)] font-mono">{u.id}</div>
                </td>
                <td className="py-2 px-1 capitalize">{u.role}</td>
                <td className="py-2 px-1">
                  <span
                    className={
                      u.state === "active"
                        ? "text-emerald-400"
                        : u.state === "banned"
                          ? "text-red-400"
                          : ""
                    }
                  >
                    {u.state}
                  </span>
                </td>
                <td className="py-2 px-1 text-xs text-[var(--color-fg-muted)]">
                  {new Date(u.created_at).toLocaleDateString()}
                </td>
                <td className="py-2 px-1 text-right space-x-1">
                  {u.role !== "contributor" && (
                    <button
                      type="button"
                      onClick={() => changeRole(u, "contributor")}
                      className="text-xs px-2 py-1 border border-[var(--color-brand-blue-2)] rounded"
                    >
                      → contributor
                    </button>
                  )}
                  {u.role !== "admin" && (
                    <button
                      type="button"
                      onClick={() => changeRole(u, "admin")}
                      className="text-xs px-2 py-1 border border-[var(--color-brand-cyan)] rounded"
                    >
                      → admin
                    </button>
                  )}
                  {u.role !== "user" && (
                    <button
                      type="button"
                      onClick={() => changeRole(u, "user")}
                      className="text-xs px-2 py-1 border border-[var(--color-brand-blue-2)] rounded"
                    >
                      → user
                    </button>
                  )}
                  {u.state !== "banned" && (
                    <button
                      type="button"
                      onClick={() => ban(u)}
                      className="text-xs px-2 py-1 border border-red-500 text-red-300 rounded"
                    >
                      Ban
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {users.length === 0 && !busy && (
              <tr>
                <td colSpan={5} className="py-6 text-center text-[var(--color-fg-muted)]">
                  No users match.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
