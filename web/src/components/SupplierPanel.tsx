import { useCallback, useEffect, useRef, useState } from "react";
import { createSupplier, findSuppliers, getJob, suppliersCsvUrl } from "../api";
import type { Job, ProductSuppliers, SupplierMode } from "../types";

const STATUS_STYLES: Record<string, string> = {
  pending: "text-paper-200/50 border-ink-600",
  searching: "text-amber border-amber/50",
  done: "text-teal border-teal/50",
  error: "text-danger border-danger/50",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "queued",
  searching: "searching…",
  done: "done",
  error: "failed",
};

/**
 * Supplier shortlisting for a finished run. Two entry points:
 *  - "FIND ONE SHARED LIST (ALL ITEMS)" — builds one supplier list from all the
 *    products and applies the SAME list to every line item.
 *  - "FIND PER ITEM" — runs a separate search and list for each line item.
 * The panel polls the job until every product is done.
 */
export default function SupplierPanel({
  job,
  onError,
  onUpdated,
}: {
  job: Job;
  onError: (msg: string) => void;
  onUpdated?: (job: Job) => void;
}) {
  const seeded = job.result?.suppliers ?? [];
  const [rows, setRows] = useState<ProductSuppliers[]>(seeded);
  const [active, setActive] = useState(false);
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set());
  const timer = useRef<number | null>(null);
  // Once this panel has started (or polled) a search, it owns `rows`; only seed
  // from the prop on first mount / when switching to a different job.
  const touched = useRef(false);

  useEffect(() => {
    if (!touched.current) setRows(seeded);
  }, [seeded]);

  useEffect(() => {
    touched.current = false;
  }, [job.id]);

  const stop = useCallback(() => {
    if (timer.current != null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    setActive(false);
  }, []);

  // Poll while a search is in flight, then stop when nothing is left to do.
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const updated = await getJob(job.id);
        const next = updated.result?.suppliers ?? [];
        if (cancelled) return;
        touched.current = true;
        setRows(next);
        const busy = next.some((r) => r.status === "searching" || r.status === "pending");
        if (!busy) {
          onUpdated?.(updated);
          stop();
          return;
        }
      } catch (e) {
        if (!cancelled) {
          onError(e instanceof Error ? e.message : String(e));
          stop();
          return;
        }
      }
      if (!cancelled) timer.current = window.setTimeout(tick, 3500);
    };
    timer.current = window.setTimeout(tick, 1500);
    return () => {
      cancelled = true;
      if (timer.current != null) window.clearTimeout(timer.current);
    };
  }, [active, job.id, onError, onUpdated, stop]);

  if (seeded.length === 0 && (job.result?.line_items_count ?? 0) === 0) return null;

  const busy = active || rows.some((r) => r.status === "searching" || r.status === "pending");
  const hasErrors = rows.some((r) => r.status === "error");
  const started = rows.length > 0;
  const doneAll = started && rows.every((r) => r.status === "done") && !busy;
  const foundTotal = rows.reduce((sum, r) => sum + (r.suppliers?.length ?? 0), 0);
  const doneCount = rows.filter((r) => r.status === "done").length;

  /** Save one found supplier into the persistent master list. */
  const saveToDirectory = async (
    key: string,
    supplier: ProductSuppliers["suppliers"][number],
    itemName?: string | null,
  ) => {
    try {
      await createSupplier({
        company_name: supplier.company_name ?? "",
        website: supplier.website ?? "",
        email: supplier.email ?? "",
        contact: supplier.contact ?? "",
        source: supplier.source ?? "",
        notes: itemName ? `found for ${itemName}` : "",
        tags: "",
      });
      setSavedKeys((prev) => new Set(prev).add(key));
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    }
  };

  const onStart = async (mode: SupplierMode) => {    touched.current = true;
    setActive(true);
    try {
      const updated = await findSuppliers(job.id, mode);
      setRows(updated.result?.suppliers ?? rows);
      onUpdated?.(updated);
    } catch (e) {
      setActive(false);
      onError(e instanceof Error ? e.message : String(e));
    }
  };

  const allLabel = !started
    ? "FIND ONE SHARED LIST (ALL ITEMS)"
    : hasErrors && !busy
      ? "RETRY SHARED LIST"
      : "RE-RUN SHARED LIST";
  const perItemLabel = hasErrors && !busy ? "RETRY PER ITEM" : "FIND PER ITEM";

  const allFailed = started && rows.every((r) => r.status === "error") && !busy;

  return (
    <div className="rounded-2xl border border-ink-700 bg-ink-900/70 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">Supplier shortlist</p>
          {started && doneAll && (
            <p className="mt-1 font-mono text-[11px] text-paper-200/40">
              {foundTotal} suppliers across {doneCount} product{doneCount === 1 ? "" : "s"} · live web search data
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {doneAll && (
            <a
              href={suppliersCsvUrl(job.id)}
              className="rounded-lg border border-ink-600 px-4 py-2 font-mono text-xs text-paper-200/70 transition hover:border-amber/50 hover:text-amber"
            >
              export CSV
            </a>
          )}
          <button
            onClick={() => onStart("per_item")}
            disabled={busy}
            title="Find a separate supplier list for each line item"
            className="rounded-lg border border-ink-600 px-4 py-2.5 font-mono text-xs text-paper-200/70 transition hover:border-amber/50 hover:text-amber disabled:cursor-not-allowed disabled:opacity-50"
          >
            {perItemLabel}
          </button>
          <button
            onClick={() => onStart("all")}
            disabled={busy}
            title="Find one supplier list and apply the same list to every item"
            className="rounded-lg bg-amber px-5 py-2.5 font-mono text-xs font-semibold text-space-950 transition hover:bg-amber-light disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "SEARCHING…" : allLabel}
          </button>
        </div>
      </div>

      {busy && (
        <div className="mt-4">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-800">
            <div
              className="h-full rounded-full bg-amber transition-all duration-500"
              style={{ width: `${doneCount === 0 ? 4 : Math.round((doneCount / rows.length) * 100)}%` }}
            />
          </div>
          <p className="mt-2 font-mono text-[11px] text-paper-200/50">
            Searching {doneCount}/{rows.length} products on Google…
          </p>
        </div>
      )}

      {allFailed && (
        <p className="mt-4 rounded-lg border border-danger/30 bg-danger/5 p-3 font-mono text-xs text-danger">
          No suppliers were found — every product failed. If the Gemini grounding quota is exhausted the
          app now falls back to normal web search automatically, so a total failure usually means that
          fallback (DuckDuckGo / Google Custom Search) was also unavailable. Each product card below shows
          the exact error.
        </p>
      )}

      <ul className="mt-4 space-y-4">
        {rows.map((row, i) => (
          <li key={i} className="rounded-xl border border-ink-800 bg-ink-800/40 p-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span
                className={[
                  "rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide",
                  STATUS_STYLES[row.status] ?? STATUS_STYLES.pending,
                ].join(" ")}
              >
                {STATUS_LABELS[row.status] ?? row.status}
              </span>
              <span className="font-mono text-sm text-paper-50">
                {row.item_no ? `#${row.item_no} ` : ""}{row.item_name ?? `Item ${i + 1}`}
              </span>
              {row.backend === "web_search" && (
                <span
                  className="rounded-full border border-amber/30 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-amber/80"
                  title="Gemini grounding quota was exhausted; found via normal web search"
                >
                  web search
                </span>
              )}
              <span className="ml-auto font-mono text-[11px] text-paper-200/50">
                {row.suppliers?.length ?? 0} supplier{row.suppliers?.length === 1 ? "" : "s"}
              </span>
            </div>

            {row.status === "error" && (
              <p className="mt-2 font-mono text-xs text-danger">{row.message}</p>
            )}
            {row.status !== "error" && (
              <p className="mt-2 font-mono text-[11px] text-paper-200/40">{row.message}</p>
            )}

            {row.status === "done" && row.suppliers.length > 0 && (
              <ul className="mt-3 divide-y divide-ink-800">
                {row.suppliers.map((s, j) => (
                  <li key={j} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 font-mono text-xs">
                    <span className="w-52 shrink-0 truncate text-paper-50" title={s.company_name}>
                      {s.company_name}
                    </span>
                    {s.website ? (
                      <a
                        href={s.website.startsWith("http") ? s.website : `https://${s.website}`}
                        target="_blank"
                        rel="noreferrer"
                        className="w-48 shrink-0 truncate text-amber/80 underline-offset-2 hover:underline"
                        title={s.website}
                      >
                        {s.website.replace(/^https?:\/\//, "")}
                      </a>
                    ) : (
                      <span className="w-48 shrink-0 truncate text-paper-200/30">—</span>
                    )}
                    {s.email ? (
                      <a href={`mailto:${s.email}`} className="w-52 shrink-0 truncate text-paper-200/80" title={s.email}>
                        {s.email}
                      </a>
                    ) : (
                      <span className="w-52 shrink-0 truncate text-paper-200/30" title="Verify before use">
                        {s.contact ? s.contact : "— verify before use"}
                      </span>
                    )}
                    {s.source && (
                      <a
                        href={s.source}
                        target="_blank"
                        rel="noreferrer"
                        className="ml-auto shrink-0 text-[10px] text-paper-200/40 underline-offset-2 hover:text-amber hover:underline"
                      >
                        source ›
                      </a>
                    )}
                    <button
                      onClick={() => saveToDirectory(`${i}:${j}`, s, row.item_name)}
                      disabled={savedKeys.has(`${i}:${j}`)}
                      title="Save this supplier to your master list"
                      className={[
                        "shrink-0 rounded border px-2 py-0.5 font-mono text-[10px] transition",
                        savedKeys.has(`${i}:${j}`)
                          ? "border-teal/40 text-teal"
                          : "border-ink-600 text-paper-200/50 hover:border-amber/50 hover:text-amber",
                      ].join(" ")}
                    >
                      {savedKeys.has(`${i}:${j}`) ? "saved ✓" : "+ list"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}