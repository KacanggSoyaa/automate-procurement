import { useEffect, useState } from "react";
import { listAllHistory } from "../api";
import type { AdminHistoryOwner } from "../types";

/** Compact relative time for a run (e.g. "3h ago", "Jun 4"). */
function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const minutes = Math.round((Date.now() - d.getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Colour of the status dot for each job state. */
const DOT: Record<string, string> = {
  done: "bg-teal",
  error: "bg-danger",
  running: "bg-amber animate-pulse-dot",
  queued: "bg-paper-200/40",
};

interface Props {
  onError: (msg: string) => void;
}

/**
 * Admin-only view of every user's saved runs, grouped by account.
 *
 * This is deliberately separate from the signed-in admin's own history rail:
 * the sidebar only ever shows the runs of the account you are logged in as.
 */
export default function AdminHistory({ onError }: Props) {
  const [owners, setOwners] = useState<AdminHistoryOwner[]>([]);
  const [loading, setLoading] = useState(true);
  const [openOwner, setOpenOwner] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listAllHistory()
      .then((data) => {
        if (active) setOwners(data);
      })
      .catch((e) => {
        if (active) onError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [onError]);

  const total = owners.reduce((sum, o) => sum + o.jobs.length, 0);

  return (
    <div className="rounded-2xl border border-ink-800 bg-ink-900/40 p-5">
      <div className="flex items-baseline justify-between gap-4">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber/80">
          User activity
        </p>
        <p className="font-mono text-[10px] text-paper-200/40">
          {total} run{total === 1 ? "" : "s"} across {owners.length} account
          {owners.length === 1 ? "" : "s"}
        </p>
      </div>

      {loading ? (
        <p className="mt-4 font-mono text-xs text-paper-200/40">loading…</p>
      ) : owners.length === 0 ? (
        <p className="mt-4 font-mono text-xs leading-relaxed text-paper-200/40">
          No runs saved yet by any account.
        </p>
      ) : (
        <ul className="mt-4 space-y-2">
          {owners.map((owner) => {
            const expanded = openOwner === owner.owner_id;
            const label = owner.display_name || owner.username;
            return (
              <li
                key={owner.owner_id || owner.username}
                className="rounded-xl border border-ink-800 bg-ink-950/50"
              >
                <button
                  onClick={() => setOpenOwner(expanded ? null : owner.owner_id)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left"
                >
                  <span className="font-mono text-xs font-semibold text-paper-50">
                    {label}
                  </span>
                  <span className="font-mono text-[10px] text-paper-200/40">
                    @{owner.username}
                  </span>
                  {owner.role === "admin" && (
                    <span className="font-mono text-[10px] text-amber/70">· admin</span>
                  )}
                  <span className="ml-auto font-mono text-[10px] text-paper-200/40">
                    {owner.jobs.length} run{owner.jobs.length === 1 ? "" : "s"}
                  </span>
                  <span className="font-mono text-[10px] text-paper-200/30">
                    {expanded ? "▲" : "▼"}
                  </span>
                </button>

                {expanded && (
                  <ul className="space-y-1 border-t border-ink-800 px-3 py-3">
                    {owner.jobs.map((job) => (
                      <li
                        key={job.id}
                        className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-ink-900"
                      >
                        <span
                          className={[
                            "h-1.5 w-1.5 shrink-0 rounded-full",
                            DOT[job.status] ?? DOT.queued,
                          ].join(" ")}
                        />
                        <span className="min-w-0 flex-1 truncate font-mono text-xs text-paper-50">
                          {job.title}
                        </span>
                        <span className="hidden min-w-0 truncate font-mono text-[10px] text-paper-200/45 sm:block">
                          {job.subtitle}
                        </span>
                        <span className="shrink-0 font-mono text-[10px] text-paper-200/40">
                          {job.line_items_count} item
                          {job.line_items_count === 1 ? "" : "s"}
                        </span>
                        <span className="shrink-0 font-mono text-[10px] text-paper-200/40">
                          {formatWhen(job.created_at)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
