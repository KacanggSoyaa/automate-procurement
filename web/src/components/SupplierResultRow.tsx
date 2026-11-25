import type { Supplier } from "../types";

interface Props {
  supplier: Supplier;
  saved: boolean;
  onSave: () => void;
}

export default function SupplierResultRow({ supplier, saved, onSave }: Props) {
  const website = supplier.website?.trim() ?? "";
  const email = supplier.email?.trim() ?? "";
  const contact = supplier.contact?.trim() ?? "";
  const source = supplier.source?.trim() ?? "";

  return (
    <li className="grid grid-cols-1 gap-2 rounded-lg border border-ink-800/70 bg-ink-900/40 p-3 font-mono text-xs lg:grid-cols-[minmax(0,9rem)_minmax(0,8rem)_minmax(0,10rem)_auto_auto] lg:items-center lg:gap-3 lg:border-0 lg:bg-transparent lg:p-0 lg:py-2">
      <div className="min-w-0">
        <p className="mb-0.5 text-[9px] uppercase tracking-wide text-paper-200/35 lg:hidden">
          company
        </p>
        <span className="block truncate text-paper-50" title={supplier.company_name}>
          {supplier.company_name || "—"}
        </span>
      </div>

      <div className="min-w-0">
        <p className="mb-0.5 text-[9px] uppercase tracking-wide text-paper-200/35 lg:hidden">
          website
        </p>
        {website ? (
          <a
            href={website.startsWith("http") ? website : `https://${website}`}
            target="_blank"
            rel="noreferrer"
            className="block truncate text-amber/80 underline-offset-2 hover:underline"
            title={website}
          >
            {website.replace(/^https?:\/\//, "")}
          </a>
        ) : (
          <span className="block truncate text-paper-200/30">—</span>
        )}
      </div>

      <div className="min-w-0">
        <p className="mb-0.5 text-[9px] uppercase tracking-wide text-paper-200/35 lg:hidden">
          contact
        </p>
        {email ? (
          <a
            href={`mailto:${email}`}
            className="block truncate text-paper-200/80"
            title={email}
          >
            {email}
          </a>
        ) : (
          <span className="block truncate text-paper-200/30" title="Verify before use">
            {contact || "— verify before use"}
          </span>
        )}
      </div>

      <div className="min-w-0">
        {source && (
          <a
            href={source}
            target="_blank"
            rel="noreferrer"
            className="text-[10px] text-paper-200/40 underline-offset-2 hover:text-amber hover:underline"
          >
            source ›
          </a>
        )}
      </div>

      <button
        onClick={onSave}
        disabled={saved}
        className={[
          "justify-self-start rounded border px-2 py-0.5 text-[10px] transition lg:justify-self-end",
          saved
            ? "border-teal/40 text-teal"
            : "border-ink-600 text-paper-200/50 hover:border-amber/50 hover:text-amber",
        ].join(" ")}
      >
        {saved ? "saved ✓" : "+ list"}
      </button>
    </li>
  );
}
