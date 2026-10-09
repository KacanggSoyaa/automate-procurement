import type { Job } from "../types";

const STATUS_STYLES: Record<string, string> = {
  queued: "text-paper-200/70 border-ink-600",
  running: "text-amber border-amber/50",
  done: "text-teal border-teal/50",
  error: "text-danger border-danger/50",
};

export default function JobPanel({ job }: { job: Job }) {
  const pct =
    job.total > 0 ? Math.min(100, Math.round((job.current / job.total) * 100)) : job.status === "done" ? 100 : 8;

  return (
    <div className="rounded-2xl border border-ink-700 bg-ink-900/70 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className={[
              "rounded-full border px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-wide",
              STATUS_STYLES[job.status] ?? STATUS_STYLES.queued,
            ].join(" ")}
          >
            {job.status}
          </span>
          <span className="font-mono text-xs text-paper-200/60">job {job.id}</span>
        </div>
        <span className="font-mono text-xs text-paper-200/50">
          {job.files.length} file{job.files.length === 1 ? "" : "s"}
        </span>
      </div>

      <p className="mt-4 font-mono text-sm text-paper-50">{job.message}</p>

      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-ink-800">
        <div
          className={[
            "h-full rounded-full transition-all duration-500",
            job.status === "error" ? "bg-danger" : job.status === "done" ? "bg-teal" : "bg-amber",
          ].join(" ")}
          style={{ width: `${pct}%` }}
        />
      </div>

      {job.error && (
        <pre className="mt-4 overflow-x-auto rounded-lg border border-danger/30 bg-danger/5 p-3 font-mono text-xs text-danger">
          {job.error}
        </pre>
      )}

      <div className="mt-4 max-h-56 overflow-y-auto rounded-lg border border-ink-800 bg-space-950 p-3 scrollbar-thin">
        {job.logs.length === 0 ? (
          <p className="font-mono text-xs text-paper-200/40">waiting for output…</p>
        ) : (
          job.logs.map((log, i) => (
            <div key={i} className="flex gap-3 font-mono text-xs leading-relaxed">
              <span className="text-ink-600">{log.ts}</span>
              <span className="text-paper-200/80">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
