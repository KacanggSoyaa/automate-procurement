import { useState } from "react";
import { login } from "../api";
import type { AuthUser } from "../types";

/**
 * Full-screen login form shown when there is no valid session. On success the
 * parent receives the authenticated user and renders the app.
 */
export default function Login({ onSuccess }: { onSuccess: (user: AuthUser) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("Enter your username and password.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onSuccess(await login(username.trim(), password));
    } catch (e) {
      let msg = e instanceof Error ? e.message : String(e);
      // FastAPI returns {"detail": "..."}; surface a clean message.
      try {
        const parsed = JSON.parse(msg);
        if (parsed?.detail) msg = parsed.detail;
      } catch {
        /* not JSON, keep as-is */
      }
      setError(msg || "Login failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-grid px-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-3 font-mono text-sm">
          <span className="text-amber">▮</span>
          <span className="font-semibold tracking-tight text-paper-50">automate</span>
          <span className="text-paper-200/40">//</span>
          <span className="text-paper-200/70">procurement</span>
        </div>

        <form
          onSubmit={submit}
          className="rounded-2xl border border-ink-700 bg-ink-900/70 p-6 backdrop-blur-xl"
        >
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber/80">Sign in</p>
          <h1 className="mt-2 font-mono text-xl font-semibold text-paper-50">Welcome back</h1>

          <label className="mt-5 flex flex-col gap-1.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-paper-200/50">
              username
            </span>
            <input
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="rounded-lg border border-ink-700 bg-ink-950/60 px-3 py-2 font-mono text-sm text-paper-50 focus:border-amber focus:outline-none"
            />
          </label>

          <label className="mt-4 flex flex-col gap-1.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-paper-200/50">
              password
            </span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="rounded-lg border border-ink-700 bg-ink-950/60 px-3 py-2 font-mono text-sm text-paper-50 focus:border-amber focus:outline-none"
            />
          </label>

          {error && (
            <p className="mt-4 rounded-lg border border-danger/30 bg-danger/5 p-3 font-mono text-xs text-danger">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="mt-5 w-full rounded-lg bg-amber px-6 py-2.5 font-mono text-sm font-semibold text-space-950 transition hover:bg-amber-light disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "SIGNING IN…" : "SIGN IN"}
          </button>

          <p className="mt-4 text-center font-mono text-[11px] leading-relaxed text-paper-200/40">
            Accounts are created by an administrator.
            <br />
            Ask your admin for credentials, or create the first admin via the CLI.
          </p>
        </form>
      </div>
    </div>
  );
}
