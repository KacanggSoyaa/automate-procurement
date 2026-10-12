import { useState } from "react";
import { addJobFiles } from "../api";
import type { Job } from "../types";

// File types accepted for appending to an existing ITB run.
const ALLOWED = [".pdf", ".docx", ".xlsx", ".xlsm", ".png", ".jpg", ".jpeg", ".webp", ".bmp"];

/** Return true when a filename has an accepted extension. */
function isAllowed(name: string): boolean {
  const lower = name.toLowerCase();
  return ALLOWED.some((ext) => lower.endsWith(ext));
}

interface Props {
  jobId: string;
  /** Called once the backend has queued the incremental reprocess. */
  onProcessed: (job: Job) => void;
  onError: (message: string) => void;
}

/**
 * Lets the user add documents/screenshots to a finished ITB run. The backend
 * reprocesses only the new files — existing line items are kept as-is.
 */
export default function AddFiles({ jobId, onProcessed, onError }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);

  /** Filter a file list down to the accepted extensions. */
  const pick = (list: FileList | null) => {
    if (!list) return;
    setFiles(Array.from(list).filter((f) => isAllowed(f.name)));
  };

  /** Upload the selected files and start the incremental reprocess. */
  const add = async () => {
    if (!files.length || busy) return;
    setBusy(true);
    try {
      const job = await addJobFiles(jobId, files);
      onProcessed(job);
      setFiles([]);
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900/70 p-4">
      <div className="flex items-center justify-between">
        <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">
          add files to this ITB
        </p>
        {files.length > 0 && (
          <span className="font-mono text-[11px] text-paper-200/40">{files.length} selected</span>
        )}
      </div>

      <p className="mt-2 font-sans text-xs leading-relaxed text-paper-200/50">
        Upload extra documents or screenshots for this run. Only the <span className="text-paper-200/80">new files</span>{" "}
        are reprocessed by Gemini — existing line items and requirements are kept, and the
        specification sheet + RFQ email are rebuilt from the combined set.
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            const input = document.createElement("input");
            input.type = "file";
            input.multiple = true;
            input.accept = ALLOWED.join(",");
            input.onchange = () => pick(input.files);
            input.click();
          }}
          disabled={busy}
          className="rounded-lg border border-ink-700 bg-ink-800 px-3 py-2 font-mono text-xs text-paper-200/80 transition hover:border-amber/50 hover:text-amber disabled:cursor-not-allowed disabled:opacity-50"
        >
          + choose files
        </button>

        {files.map((f) => (
          <span
            key={f.name}
            className="flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-800 px-3 py-1.5 font-mono text-xs text-paper-200/80"
          >
            <span className="max-w-[200px] truncate">{f.name}</span>
            <span className="text-paper-200/40">{formatBytes(f.size)}</span>
          </span>
        ))}
      </div>

      <button
        type="button"
        onClick={add}
        disabled={busy || !files.length}
        className="mt-3 rounded-lg bg-amber px-4 py-2 font-mono text-xs font-semibold text-space-950 transition hover:bg-amber-light disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? "PROCESSING…" : "Add & reprocess"}
      </button>
    </div>
  );
}

/** Format a byte count as a short human-readable string (B / KB / MB). */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}