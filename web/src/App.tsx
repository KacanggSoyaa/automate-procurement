import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createJob,
  deleteHistory,
  getJob,
  getQuotaStatus,
  listHistory,
  renameHistory,
} from "./api";
import AddFiles from "./components/AddFiles";
import DropZone from "./components/DropZone";
import HistorySidebar from "./components/HistorySidebar";
import JobPanel from "./components/JobPanel";
import Results from "./components/Results";
import RfqEmails from "./components/RfqEmails";
import SettingsPanel, { parseSkipList } from "./components/SettingsPanel";
import SupplierPanel from "./components/SupplierPanel";
import VersionsAudit from "./components/VersionsAudit";
import type { HistoryItem, Job, QuotaStatus } from "./types";

/** Format a byte count as a short human-readable string (B / KB / MB). */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Root component: holds the selected files, starts a processing job and polls
 * it until it finishes, then renders the results. Past runs are listed in the
 * history sidebar on the left.
 */
export default function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [pollId, setPollId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [includeImages, setIncludeImages] = useState(true);
  const [skipFiles, setSkipFiles] = useState("");
  const [quota, setQuota] = useState<QuotaStatus | null>(null);

  // Total size of the selected files, shown in the file summary bar.
  const totalSize = useMemo(() => files.reduce((sum, f) => sum + f.size, 0), [files]);
  const running = busy || pollId != null;

  /** Reload the saved-run history from the backend. */
  const loadHistory = useCallback(async () => {
    try {
      setHistory(await listHistory());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  // Load history once on mount.
  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Refresh the Google-Search grounding quota badge every 30s (cheap, no API cost).
  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      try {
        const q = await getQuotaStatus();
        if (!cancelled) setQuota(q);
      } catch {
        /* backend not up yet; try again next tick */
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  // Poll the in-flight job every 1.5s until it is done or has errored. This is
  // keyed on the job id (not the displayed job) so navigating to history
  // mid-run keeps the run tracked and refreshes the sidebar on completion.
  useEffect(() => {
    if (!pollId) return;
    let timer: number;
    let cancelled = false;

    const tick = async () => {
      try {
        const updated = await getJob(pollId);
        if (cancelled) return;
        setJob((prev) => (prev && prev.id === pollId ? updated : prev));
        if (updated.status === "done" || updated.status === "error") {
          setPollId(null);
          loadHistory();
          return;
        }
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      }
      timer = window.setTimeout(tick, 1500);
    };

    timer = window.setTimeout(tick, 1500);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [pollId, loadHistory]);

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
      const j = await createJob(files, { includeImages, skipFiles: parseSkipList(skipFiles) });
      setJob(j);
      setPollId(j.id);
      setSidebarOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  /** Open a saved run from the sidebar and show its results. */
  const openHistory = async (id: string) => {
    setError(null);
    setSidebarOpen(false);
    try {
      setJob(await getJob(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  /** Delete a saved run from history. */
  const removeHistory = async (id: string) => {
    try {
      await deleteHistory(id);
      if (job?.id === id) setJob(null);
      await loadHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  /** Rename a saved run in history. */
  const renameRun = async (id: string, title: string) => {
    try {
      await renameHistory(id, title);
      await loadHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  /** Set up polling for an incremental reprocess after files were added. */
  const onFilesAdded = (updated: Job) => {
    setJob(updated);
    setPollId(updated.id);
  };

  /** Start a fresh run: clear the current selection and results. */
  const startNew = () => {
    setFiles([]);
    setJob(null);
    setError(null);
    setSkipFiles("");
    setSidebarOpen(false);
  };

  return (
    <div className="flex min-h-screen bg-grid">
      <HistorySidebar
        items={history}
        activeId={job?.id ?? null}
        loading={historyLoading}
        open={sidebarOpen}
        running={running}
        onClose={() => setSidebarOpen(false)}
        onNew={startNew}
        onSelect={openHistory}
        onDelete={removeHistory}
        onRename={renameRun}
      />

      <div className="min-w-0 flex-1">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <header className="flex items-center justify-between border-b border-ink-800 pb-4">
            <div className="flex items-center gap-3 font-mono text-sm">
              <button
                onClick={() => setSidebarOpen(true)}
                className="flex h-7 w-7 items-center justify-center rounded border border-ink-700 text-paper-200/60 transition hover:border-amber/50 hover:text-amber md:hidden"
                title="Open history"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M3 6h18M3 12h18M3 18h18" />
                </svg>
              </button>
              <span className="text-amber">▮</span>
              <span className="font-semibold tracking-tight text-paper-50">automate</span>
              <span className="text-paper-200/40">//</span>
              <span className="text-paper-200/70">procurement</span>
            </div>
            <div className="flex items-center gap-2 font-mono text-[11px] text-paper-200/50">
              <span className="h-1.5 w-1.5 rounded-full bg-teal animate-pulse-dot" />
              gemini vision pipeline
              <span className="text-paper-200/25">·</span>
              <a
                href={quota?.link ?? "https://ai.dev/rate-limit"}
                target="_blank"
                rel="noreferrer"
                title={
                  quota?.detail ??
                  (quota?.state === "unknown"
                    ? "Quota not checked yet — run a supplier search"
                    : "Google-Search grounding quota (last check)")
                }
                className="flex items-center gap-1.5 transition hover:text-paper-100"
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    quota?.state === "exhausted"
                      ? "bg-danger"
                      : quota?.state === "ok"
                        ? "bg-teal"
                        : "bg-paper-200/30"
                  }`}
                />
                quota:{" "}
                {!quota
                  ? "…"
                  : quota.state === "unknown"
                    ? "not checked"
                    : quota.state}
              </a>
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
              PDFs, Word / Excel files and images are read, line items are separated from requirements by Gemini, and a
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

              <SettingsPanel
                names={files.map((f) => f.name)}
                value={skipFiles}
                onChange={setSkipFiles}
                disabled={running}
              />

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
              {job.status === "done" && (
                <AddFiles
                  jobId={job.id}
                  onProcessed={onFilesAdded}
                  onError={(msg) => setError(msg)}
                />
              )}
              {job.status === "done" && <Results job={job} />}
              {job.status === "done" && <SupplierPanel job={job} onError={(msg) => setError(msg)} onUpdated={setJob} />}
              {job.status === "done" && <VersionsAudit job={job} />}
              {job.status === "done" && <RfqEmails emails={job.result?.rfq_emails ?? []} />}
            </div>
          )}

          <footer className="mt-16 border-t border-ink-800 pt-4 font-mono text-[11px] text-paper-200/40">
            automate // procurement · local pipeline · powered by Gemini
          </footer>
        </div>
      </div>
    </div>
  );
}
