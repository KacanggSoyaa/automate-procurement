import { downloadUrl } from "../api";
import type { Job } from "../types";

/** Small stat card used in the results summary grid. */
function Stat({ label, value, accent }: { label: string; value: number | string; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900/70 p-4">
      <p className="font-mono text-[11px] uppercase tracking-wide text-paper-200/50">{label}</p>
      <p className={["mt-1 font-mono text-2xl font-semibold", accent ? "text-amber" : "text-paper-50"].join(" ")}>
        {value}
      </p>
    </div>
  );
}

/** Renders the finished job: stats, metadata, item table, download + evidence. */
export default function Results({ job }: { job: Job }) {
  const result = job.result;
  if (!result) return null;
  const meta = result.meta ?? {};

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Files" value={result.files_processed} />
        <Stat label="Line items" value={result.line_items_count} accent />
        <Stat label="Technical reqs" value={result.technical_count} />
        <Stat label="Submission rules" value={result.submission_count} />
      </div>

      {(meta.project_ref || meta.buyer || meta.delivery_location) && (
        <div className="rounded-xl border border-ink-700 bg-ink-900/70 p-4 font-mono text-xs text-paper-200/80">
          {meta.project_ref && (
            <p>
              <span className="text-paper-200/50">PROJECT REF: </span>
              {meta.project_ref}
              {meta.project_title ? ` — ${meta.project_title}` : ""}
            </p>
          )}
          {meta.buyer && (
            <p>
              <span className="text-paper-200/50">BUYER: </span>
              {meta.buyer}
            </p>
          )}
          {meta.delivery_location && (
            <p>
              <span className="text-paper-200/50">DELIVERY: </span>
              {meta.delivery_location}
            </p>
          )}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-ink-700">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="bg-ink-800 font-mono text-[11px] uppercase tracking-wide text-paper-200/60">
              <th className="px-3 py-2">No.</th>
              <th className="px-3 py-2">Item Name</th>
              <th className="px-3 py-2">Item No.</th>
              <th className="px-3 py-2">Qty</th>
              <th className="px-3 py-2">UOM</th>
            </tr>
          </thead>
          <tbody>
            {result.line_items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center font-mono text-xs text-paper-200/40">
                  No line items identified.
                </td>
              </tr>
            ) : (
              result.line_items.map((item, i) => (
                <tr key={i} className="border-t border-ink-800 font-mono text-xs text-paper-50">
                  <td className="px-3 py-2 text-paper-200/60">{item.item_no ?? i + 1}</td>
                  <td className="px-3 py-2">{item.item_name ?? item.description ?? "—"}</td>
                  <td className="px-3 py-2 text-paper-200/70">{item.item_number ?? "—"}</td>
                  <td className="px-3 py-2 text-center">{item.qty ?? "—"}</td>
                  <td className="px-3 py-2 text-center">{item.uom ?? "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {result.has_output && (
        <a
          href={downloadUrl(job.id)}
          className="inline-flex items-center gap-2 rounded-lg bg-amber px-5 py-2.5 font-mono text-sm font-semibold text-space-950 transition hover:bg-amber-light"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3v12" />
            <path d="m7 10 5 5 5-5" />
            <path d="M5 21h14" />
          </svg>
          Download specification sheet (.docx)
        </a>
      )}

      {result.source_files.length > 0 && (
        <div className="rounded-lg border border-ink-700 bg-ink-900/40 p-4">
          <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-wide text-paper-200/70">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <path d="M14 2v6h6" />
            </svg>
            Source documents (evidence)
          </div>
          <ul className="space-y-1">
            {result.source_files.map((name) => (
              <li key={name} className="font-mono text-xs text-paper-200">
                <span className="text-amber">›</span> {name}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
