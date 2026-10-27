import { Fragment, useEffect, useState } from "react";
import { deleteJobItem, downloadUrl, updateJobItem } from "../api";
import type { Job, LineItem, LineItemEdit } from "../types";

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

/** One text input in the inline line-item editor. */
function Field({
  label, value, onChange, className = "",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      <span className="font-mono text-[10px] uppercase tracking-wide text-paper-200/50">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-ink-700 bg-ink-950/60 px-2.5 py-1.5 font-mono text-xs text-paper-50 focus:border-amber focus:outline-none"
      />
    </label>
  );
}

function toEdit(item: LineItem): LineItemEdit {
  return {
    item_no: item.item_no ?? "",
    item_name: item.item_name ?? "",
    item_number: item.item_number ?? "",
    description: item.description ?? "",
    qty: item.qty ?? "",
    uom: item.uom ?? "",
  };
}

/** Renders the finished job: stats, metadata, item table, download + evidence. */
export default function Results({
  job, onUpdated,
}: {
  job: Job;
  onUpdated: (job: Job) => void;
}) {
  const result = job.result;
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState<LineItemEdit | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    setEditing(null);
    setDraft(null);
    setDeleting(null);
    setFormError(null);
    setNotice(null);
  }, [job.id]);

  if (!result) return null;
  const meta = result.meta ?? {};

  const startEdit = (index: number, item: LineItem) => {
    setEditing(index);
    setDraft(toEdit(item));
    setFormError(null);
    setNotice(null);
  };

  const cancelEdit = () => {
    setEditing(null);
    setDraft(null);
    setFormError(null);
  };

  const setField = (key: keyof LineItemEdit, value: string) => {
    setDraft((d) => (d ? { ...d, [key]: value } : d));
  };

  const saveEdit = async () => {
    if (editing === null || !draft) return;
    setSaving(true);
    setFormError(null);
    setNotice(null);
    try {
      const updated = await updateJobItem(job.id, editing, draft);
      onUpdated(updated);
      setNotice(`Item ${editing + 1} updated — specification sheet and RFQ email rebuilt.`);
      setEditing(null);
      setDraft(null);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Could not update this item.");
    } finally {
      setSaving(false);
    }
  };

  const removeItem = async (index: number, item: LineItem) => {
    const label = item.item_name || item.item_number || `item ${index + 1}`;
    if (!window.confirm(`Delete "${label}"? This rebuilds the specification sheet and RFQ email.`)) {
      return;
    }
    if (editing !== null) cancelEdit();
    setDeleting(index);
    setFormError(null);
    setNotice(null);
    try {
      const updated = await deleteJobItem(job.id, index);
      onUpdated(updated);
      setNotice(`Item ${index + 1} deleted — specification sheet and RFQ email rebuilt.`);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Could not delete this item.");
    } finally {
      setDeleting(null);
    }
  };

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

      {notice && (
        <p className="rounded-lg border border-teal/30 bg-teal/5 p-2.5 font-mono text-[11px] text-teal">
          {notice}
        </p>
      )}

      {formError && editing === null && (
        <p className="rounded-lg border border-danger/30 bg-danger/5 p-2.5 font-mono text-[11px] text-danger">
          {formError}
        </p>
      )}

      <div className="overflow-x-auto rounded-xl border border-ink-700">
        <table className="w-full min-w-[740px] border-collapse text-left">
          <thead>
            <tr className="bg-ink-800 font-mono text-[11px] uppercase tracking-wide text-paper-200/60">
              <th className="px-3 py-2">No.</th>
              <th className="px-3 py-2">Item Name</th>
              <th className="px-3 py-2">Item No.</th>
              <th className="px-3 py-2">Qty</th>
              <th className="px-3 py-2">UOM</th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {result.line_items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center font-mono text-xs text-paper-200/40">
                  No line items identified.
                </td>
              </tr>
            ) : (
              result.line_items.map((item, i) => (
                <Fragment key={i}>
                  <tr className="border-t border-ink-800 font-mono text-xs text-paper-50 transition hover:bg-ink-800/30">
                    <td className="px-3 py-2 text-paper-200/60">{item.item_no ?? i + 1}</td>
                    <td className="px-3 py-2">{item.item_name ?? item.description ?? "—"}</td>
                    <td className="px-3 py-2 text-paper-200/70">{item.item_number ?? "—"}</td>
                    <td className="px-3 py-2 text-center">{item.qty ?? "—"}</td>
                    <td className="px-3 py-2 text-center">{item.uom ?? "—"}</td>
                    <td className="px-3 py-2">
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => startEdit(i, item)}
                          disabled={saving || deleting !== null}
                          className="rounded border border-ink-600 px-3 py-1 font-mono text-[11px] text-paper-200/60 transition hover:border-amber/50 hover:text-amber disabled:opacity-50"
                        >
                          edit
                        </button>
                        <button
                          type="button"
                          onClick={() => removeItem(i, item)}
                          disabled={saving || deleting !== null}
                          className="rounded border border-ink-600 px-3 py-1 font-mono text-[11px] text-paper-200/60 transition hover:border-danger/50 hover:text-danger disabled:opacity-50"
                        >
                          {deleting === i ? "deleting…" : "delete"}
                        </button>
                      </div>
                    </td>
                  </tr>
                  {editing === i && draft && (
                    <tr className="border-t border-ink-800 bg-ink-800/30">
                      <td colSpan={6} className="px-3 py-3">
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-6">
                          <Field
                            label="No."
                            value={draft.item_no}
                            onChange={(v) => setField("item_no", v)}
                            className="sm:col-span-1"
                          />
                          <Field
                            label="Item name"
                            value={draft.item_name}
                            onChange={(v) => setField("item_name", v)}
                            className="sm:col-span-3"
                          />
                          <Field
                            label="Item no."
                            value={draft.item_number}
                            onChange={(v) => setField("item_number", v)}
                            className="sm:col-span-2"
                          />
                          <Field
                            label="Qty"
                            value={draft.qty}
                            onChange={(v) => setField("qty", v)}
                            className="sm:col-span-1"
                          />
                          <Field
                            label="UOM"
                            value={draft.uom}
                            onChange={(v) => setField("uom", v)}
                            className="sm:col-span-1"
                          />
                          <label className="flex flex-col gap-1 sm:col-span-4">
                            <span className="font-mono text-[10px] uppercase tracking-wide text-paper-200/50">
                              Description
                            </span>
                            <textarea
                              value={draft.description}
                              onChange={(e) => setField("description", e.target.value)}
                              rows={2}
                              className="resize-y rounded border border-ink-700 bg-ink-950/60 px-2.5 py-1.5 font-mono text-xs text-paper-50 focus:border-amber focus:outline-none"
                            />
                          </label>
                        </div>
                        {formError && (
                          <p className="mt-2 font-mono text-[11px] text-danger">{formError}</p>
                        )}
                        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                          <p className="font-mono text-[10px] text-paper-200/40">
                            Saving rebuilds the specification sheet and RFQ email.
                          </p>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={cancelEdit}
                              disabled={saving}
                              className="rounded-lg border border-ink-600 px-4 py-1.5 font-mono text-xs text-paper-200/60 transition hover:text-paper-100 disabled:opacity-50"
                            >
                              cancel
                            </button>
                            <button
                              type="button"
                              onClick={saveEdit}
                              disabled={saving}
                              className="rounded-lg bg-amber px-4 py-1.5 font-mono text-xs font-semibold text-space-950 transition hover:bg-amber-light disabled:opacity-50"
                            >
                              {saving ? "saving…" : "save"}
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
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
