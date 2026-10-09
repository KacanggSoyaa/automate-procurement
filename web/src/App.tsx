import { useEffect, useMemo, useState } from "react";
import { createJob, getJob } from "./api";
import DropZone from "./components/DropZone";
import JobPanel from "./components/JobPanel";
import Results from "./components/Results";
import type { Job } from "./types";

/** Format a byte count as a short human-readable string (B / KB / MB). */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Root component: holds the selected files, starts a processing job and polls
 * it until it finishes, then renders the results.
 */
export default function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [includeImages, setIncludeImages] = useState(true);

  // Total size of the selected files, shown in the file summary bar.
  const totalSize = useMemo(() => files.reduce((sum, f) => sum + f.size, 0), [files]);
  const running = busy || (job != null && (job.status === "queued" || job.status === "running"));

  // Poll the job every 1.5s until it is done or has errored.
  useEffect(() => {
    if (!job || job.status === "done" || job.status === "error") return;
    const timer = setTimeout(async () => {
      try {
        setJob(await getJob(job.id));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    }, 1500);
    return () => clearTimeout(timer);
  }, [job]);

  /** Merge newly dropped files into the list, skipping duplicate names. */
  const onFiles = (incoming: File[]) => {
    const merged = [...files];
    const seen = new Set(files.map((f) => f.name));
    for (const f of incoming) {
      if (!seen.has(f.name)) {
        merged.push(f);
        seen.add(f.name);
      }
    }
    setFiles(merged);
    setJob(null);
    setError(null);
  };

  /** Upload the selected files and start a processing job. */
  const process = async () => {
    if (!files.length) return;
    setBusy(true);
    setError(null);
    setJob(null);
    try {
      const j = await createJob(files, { includeImages });
      setJob(j);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-grid">
      <div className="mx-auto max-w-4xl px-6 py-10">
        <header className="flex items-center justify-between border-b border-ink-800 pb-4">
          <div className="flex items-center gap-2 font-mono text-sm">
            <span className="text-amber">▮</span>
            <span className="font-semibold tracking-tight text-paper-50">automate</span>
            <span className="text-paper-200/40">//</span>
            <span className="text-paper-200/70">procurement</span>
          </div>
          <div className="flex items-center gap-2 font-mono text-[11px] text-paper-200/50">
            <span className="h-1.5 w-1.5 rounded-full bg-teal animate-pulse-dot" />
            gemini vision pipeline
          </div>
        </header>

        <section className="py-10">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber/80">Step 01 — 03</p>
          <h1 className="mt-3 font-mono text-3xl font-semibold leading-tight text-paper-50 sm:text-4xl">
            Drop an ITB folder.
            <br />
            Get a spec sheet.
          </h1>
          <p className="mt-4 max-w-2xl font-sans text-sm leading-relaxed text-paper-200/70">
            Upload your Invitation To Bid documents and screenshots. Everything runs in the background —
            PDFs and images are read, line items are separated from requirements by Gemini, and a
            formatted RFQ specification sheet comes out the other side.
          </p>
        </section>

        <DropZone onFiles={onFiles} disabled={running} />

        {files.length > 0 && (
          <div className="mt-5 rounded-2xl border border-ink-700 bg-ink-900/70 p-5">
            <div className="flex items-center justify-between">
              <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">
                {files.length} file{files.length === 1 ? "" : "s"} · {formatBytes(totalSize)}
              </p>
              <button
                className="font-mono text-xs text-paper-200/50 transition hover:text-danger"
                onClick={() => {
                  setFiles([]);
                  setJob(null);
                  setError(null);
                }}
                disabled={running}
              >
                clear
              </button>
            </div>

            <ul className="mt-3 flex flex-wrap gap-2">
              {files.map((f) => (
                <li
                  key={f.name}
                  className="flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-800 px-3 py-1.5 font-mono text-xs text-paper-200/80"
                >
                  <span className="max-w-[240px] truncate">{f.name}</span>
                  <span className="text-paper-200/40">{formatBytes(f.size)}</span>
                </li>
              ))}
            </ul>

            <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
              <label className="flex items-center gap-2 font-mono text-xs text-paper-200/70">
                <input
                  type="checkbox"
                  checked={includeImages}
                  onChange={(e) => setIncludeImages(e.target.checked)}
                  disabled={running}
                  className="h-4 w-4 accent-[var(--color-amber)]"
                />
                read images &amp; screenshots with Gemini vision
              </label>

              <button
                onClick={process}
                disabled={running}
                className="rounded-lg bg-amber px-6 py-2.5 font-mono text-sm font-semibold text-space-950 transition hover:bg-amber-light disabled:cursor-not-allowed disabled:opacity-50"
              >
                {running ? "PROCESSING…" : "RUN PIPELINE"}
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-5 rounded-xl border border-danger/30 bg-danger/5 p-4 font-mono text-xs text-danger">
            {error}
          </div>
        )}

        {job && (
          <div className="mt-5 space-y-5">
            <JobPanel job={job} />
            {job.status === "done" && <Results job={job} />}
          </div>
        )}

        <footer className="mt-16 border-t border-ink-800 pt-4 font-mono text-[11px] text-paper-200/40">
          automate // procurement · local pipeline · powered by Gemini
        </footer>
      </div>
    </div>
  );
}
