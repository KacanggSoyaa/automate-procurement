import { downloadVersionUrl } from "../api";
import type { Job } from "../types";

const REASON_LABELS: Record<string, string> = {
  run: "Initial run",
  reprocess: "Incremental reprocess",
  edit: "Manual item edit",
  delete: "Item deleted",
};

/** Render "2026-10-12T14:03:05" as "2026-10-12 14:03" for narrow columns. */
function fmtTs(ts: string): string {
  return ts ? ts.replace("T", " ").slice(0, 16) : "—";
}

/**
 * Compliance panel for a finished job: every saved version of the output
 * (downloadable as a zip snapshot) plus the append-only audit trail of what
 * happened to this run and when.
 */
export default function VersionsAudit({ job }: { job: Job }) {
  const versions = job.versions ?? [];
  const audit = job.audit ?? [];
  if (versions.length === 0 && audit.length === 0) return null;
  const latestTag = versions.length > 0 ? versions[versions.length - 1].tag : null;

  return (
    <div className="rounded-2xl border border-ink-700 bg-ink-900/70 p-6">
      <div className="flex items-center justify-between">
        <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">
          Versions &amp; audit trail
        </p>
        {latestTag && (
          <span className="font-mono text-[11px] text-teal">current: {latestTag}</span>
        )}
      </div>

      {versions.length > 0 && (
        <ul className="mt-4 space-y-2">
          {[...versions].reverse().map((v, i) => (
            <li
              key={v.id}
              className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-ink-800 bg-ink-800/40 px-3 py-2 font-mono text-xs"
            >
              <span className="font-semibold text-amber">{v.tag}</span>
              <span className="text-paper-200/70">{REASON_LABELS[v.reason] ?? v.reason}</span>
              <span className="text-paper-200/40">{fmtTs(v.ts)}</span>
              <span className="text-paper-200/70">
                {v.line_items_count} item{v.line_items_count === 1 ? "" : "s"} · {v.files_processed} file
                {v.files_processed === 1 ? "" : "s"}
              </span>
              {i === 0 ? (
                <span className="ml-auto text-teal">downloads as current</span>
              ) : (
                <a
                  href={downloadVersionUrl(job.id, v.id)}
                  className="ml-auto flex items-center gap-1.5 text-paper-200/70 transition hover:text-amber"
                  title={`Download ${v.tag} snapshot (zip)`}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 3v12" />
                    <path d="m7 10 5 5 5-5" />
                    <path d="M5 21h14" />
                  </svg>
                  download v{String(v.id).padStart(2, "0")}
                </a>
              )}
            </li>
          ))}
        </ul>
      )}

      {audit.length > 0 && (
        <ul className="mt-5 space-y-0">
          {[...audit].reverse().map((ev, i) => (
            <li key={i} className="flex gap-3 py-1.5 font-mono text-xs">
              <span className="w-[112px] shrink-0 pt-0.5 text-paper-200/40">{fmtTs(ev.ts)}</span>
              <span className="shrink-0 text-amber">›</span>
              <span className="text-paper-200/85">
                <span className="text-teal">{ev.action}</span>
                {ev.version != null ? ` [v${String(ev.version).padStart(2, "0")}]` : ""}
                {ev.detail ? ` — ${ev.detail}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}