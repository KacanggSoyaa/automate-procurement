import { useState } from "react";
import { createSupplier, searchSuppliersByName } from "../api";
import type { Supplier } from "../types";
import SupplierResultRow from "./SupplierResultRow";

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
        <ul className="mt-5 space-y-2 lg:space-y-0 lg:divide-y lg:divide-ink-800">
          {suppliers.map((s, i) => (
            <SupplierResultRow
              key={i}
              supplier={s}
              saved={savedKeys.has(i)}
              onSave={() => save(i, s)}
            />
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