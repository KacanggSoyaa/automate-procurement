import { useEffect, useState } from "react";
import { createUser, deleteUser, listUsers, setUserPassword } from "../api";
import type { AuthUser } from "../types";

/**
 * Admin-only section for managing accounts: create users, reset passwords and
 * delete accounts. Non-admins never reach this (the tab is admin-gated).
 */
export default function UsersAdmin({
  currentUser,
  onError,
}: {
  currentUser: AuthUser;
  onError: (msg: string) => void;
}) {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<"user" | "admin">("user");
  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = async () => {
    try {
      setUsers(await listUsers());
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const flash = (msg: string) => {
    setNotice(msg);
    window.setTimeout(() => setNotice((c) => (c === msg ? null : c)), 2500);
  };

  const add = async () => {
    if (!username.trim() || password.length < 6) {
      onError("A username and a password of at least 6 characters are required.");
      return;
    }
    setCreating(true);
    try {
      await createUser({ username: username.trim(), password, display_name: displayName, role });
      setUsername("");
      setPassword("");
      setDisplayName("");
      setRole("user");
      await load();
      flash("user created");
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  };

  const resetPassword = async (u: AuthUser) => {
    const next = window.prompt(`New password for "${u.username}" (min 6 chars):`);
    if (next == null) return;
    if (next.length < 6) {
      onError("Password must be at least 6 characters.");
      return;
    }
    setBusyId(u.id);
    try {
      await setUserPassword(u.id, next);
      flash(`password reset for ${u.username}`);
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (u: AuthUser) => {
    if (!window.confirm(`Delete user "${u.username}"? This cannot be undone.`)) return;
    setBusyId(u.id);
    try {
      await deleteUser(u.id);
      setUsers((prev) => prev.filter((x) => x.id !== u.id));
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="rounded-2xl border border-ink-700 bg-ink-900/70 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">User accounts</p>
          <p className="mt-1 font-mono text-[11px] text-paper-200/40">
            {users.length} account{users.length === 1 ? "" : "s"} · accounts are admin-created
          </p>
        </div>
      </div>

      {notice && (
        <p className="mt-3 rounded-lg border border-teal/30 bg-teal/5 p-2.5 font-mono text-[11px] text-teal">
          {notice}
        </p>
      )}

      {/* Create form */}
      <div className="mt-4 rounded-xl border border-ink-700 bg-ink-800/40 p-4">
        <p className="font-mono text-[10px] uppercase tracking-wide text-paper-200/50">add a user</p>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="username"
            className="rounded border border-ink-700 bg-ink-950/60 px-2.5 py-1.5 font-mono text-xs text-paper-50 placeholder:text-paper-200/25 focus:border-amber focus:outline-none"
          />
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="display name (optional)"
            className="rounded border border-ink-700 bg-ink-950/60 px-2.5 py-1.5 font-mono text-xs text-paper-50 placeholder:text-paper-200/25 focus:border-amber focus:outline-none"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="password (min 6 chars)"
            className="rounded border border-ink-700 bg-ink-950/60 px-2.5 py-1.5 font-mono text-xs text-paper-50 placeholder:text-paper-200/25 focus:border-amber focus:outline-none"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as "user" | "admin")}
            className="rounded border border-ink-700 bg-ink-950/60 px-2.5 py-1.5 font-mono text-xs text-paper-50 focus:border-amber focus:outline-none"
          >
            <option value="user">user</option>
            <option value="admin">admin</option>
          </select>
        </div>
        <div className="mt-3 flex justify-end">
          <button
            onClick={add}
            disabled={creating}
            className="rounded-lg bg-amber px-5 py-2 font-mono text-xs font-semibold text-space-950 transition hover:bg-amber-light disabled:opacity-50"
          >
            {creating ? "CREATING…" : "+ CREATE USER"}
          </button>
        </div>
      </div>

      {/* List */}
      {loading ? (
        <p className="mt-4 font-mono text-xs text-paper-200/40">loading…</p>
      ) : (
        <ul className="mt-4 divide-y divide-ink-800">
          {users.map((u) => (
            <li key={u.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-3 font-mono text-xs">
              <span className="w-40 shrink-0 truncate text-paper-50" title={u.username}>
                {u.username}
              </span>
              <span className="w-40 shrink-0 truncate text-paper-200/60" title={u.display_name}>
                {u.display_name || "—"}
              </span>
              <span
                className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide ${
                  u.role === "admin" ? "border-amber/40 text-amber" : "border-ink-600 text-paper-200/50"
                }`}
              >
                {u.role}
              </span>
              {u.id === currentUser.id && (
                <span className="text-[10px] text-teal">you</span>
              )}
              <span className="ml-auto flex shrink-0 items-center gap-1">
                <button
                  onClick={() => resetPassword(u)}
                  disabled={busyId === u.id}
                  className="rounded border border-ink-600 px-3 py-1 text-[11px] text-paper-200/60 transition hover:border-amber/50 hover:text-amber disabled:opacity-50"
                >
                  reset password
                </button>
                <button
                  onClick={() => remove(u)}
                  disabled={busyId === u.id || u.id === currentUser.id}
                  title={u.id === currentUser.id ? "You cannot delete your own account" : "Delete user"}
                  className="rounded border border-ink-600 px-3 py-1 text-[11px] text-paper-200/60 transition hover:border-danger/50 hover:text-danger disabled:cursor-not-allowed disabled:opacity-40"
                >
                  delete
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
