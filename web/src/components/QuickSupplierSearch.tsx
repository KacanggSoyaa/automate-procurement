import { useState } from "react";
import { createSupplier, searchSuppliersByName } from "../api";
import type { Supplier } from "../types";

export default function QuickSupplierSearch({ onError }: { onError: (msg: string) => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [itemName, setItemName] = useState("");
  const [backend, setBackend] = useState<string | null>(null);
  const [savedKeys, setSavedKeys] = useState<Set<number>>(new Set());

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setSuppliers([]);
    try {
      const res = await searchSuppliersByName(name.trim(), description.trim());
      setItemName(res.item_name);
      setSuppliers(res.suppliers ?? []);
      setBackend(res.backend ?? null);
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const save = async (idx: number, s: Supplier) => {
    try {
      await createSupplier({
        company_name: s.company_name ?? "",
        website: s.website ?? "",
        email: s.email ?? "",
        contact: s.contact ?? "",
        source: s.source ?? "",
        notes: itemName ? `found for ${itemName}` : "",
        tags: "",
      });
      setSavedKeys((prev) => new Set(prev).add(idx));
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="rounded-2xl border border-ink-700 bg-ink-900/70 p-6">
      <form onSubmit={run} className="space-y-3">
        <div>
          <label className="font-mono text-xs uppercase tracking-wide text-paper-200/50">Item name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. centrifugal pump"
            className="mt-1 w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 font-mono text-sm text-paper-100"
          />
        </div>
        <div>
          <label className="font-mono text-xs uppercase tracking-wide text-paper-200/50">Description (optional)</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="optional context"
            className="mt-1 w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 font-mono text-sm text-paper-100"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !name.trim()}
          className="rounded-lg bg-amber px-5 py-2.5 font-mono text-xs font-semibold text-space-950 disabled:opacity-50"
        >
          {loading ? "SEARCHING…" : "FIND SUPPLIERS"}
        </button>
      </form>

      {suppliers.length > 0 && (
        <ul className="mt-5 divide-y divide-ink-800">
          {suppliers.map((s, i) => (
            <li key={i} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 font-mono text-xs">
              <span className="w-52 shrink-0 truncate text-paper-50" title={s.company_name}>
                {s.company_name}
              </span>
              {s.website ? (
                <a
                  href={s.website.startsWith("http") ? s.website : `https://${s.website}`}
                  target="_blank"
                  rel="noreferrer"
                  className="w-48 shrink-0 truncate text-amber/80 underline-offset-2 hover:underline"
                >
                  {s.website.replace(/^https?:\/\//, "")}
                </a>
              ) : (
                <span className="w-48 shrink-0 truncate text-paper-200/30">—</span>
              )}
              {s.email ? (
                <a href={`mailto:${s.email}`} className="w-52 shrink-0 truncate text-paper-200/80">
                  {s.email}
                </a>
              ) : (
                <span className="w-52 shrink-0 truncate text-paper-200/30">
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
                onClick={() => save(i, s)}
                disabled={savedKeys.has(i)}
                className={[
                  "shrink-0 rounded border px-2 py-0.5 font-mono text-[10px] transition",
                  savedKeys.has(i)
                    ? "border-teal/40 text-teal"
                    : "border-ink-600 text-paper-200/50 hover:border-amber/50 hover:text-amber",
                ].join(" ")}
              >
                {savedKeys.has(i) ? "saved ✓" : "+ list"}
              </button>
            </li>
          ))}
        </ul>
      )}
      {!loading && suppliers.length === 0 && itemName && (
        <p className="mt-4 font-mono text-xs text-paper-200/50">No suppliers found.</p>
      )}
      {backend && suppliers.length > 0 && (
        <p className="mt-3 font-mono text-[10px] text-paper-200/40">
          via {backend === "web_search" ? "web search" : "live AI search"}
        </p>
      )}
    </div>
  );
}