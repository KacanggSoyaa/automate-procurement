import { useEffect, useRef, useState } from "react";
import type { HistoryItem } from "../types";

/** Compact relative time for history entries (e.g. "3h ago", "Jun 4"). */
function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const minutes = Math.round((Date.now() - d.getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Colour of the status dot for each job state. */
const DOT: Record<string, string> = {
  done: "bg-teal",
  error: "bg-danger",
  running: "bg-amber animate-pulse-dot",
  queued: "bg-paper-200/40",
};

interface Props {
  items: HistoryItem[];
  activeId: string | null;
  loading: boolean;
  open: boolean;
  running: boolean;
  onClose: () => void;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}

/**
 * Left-hand history rail listing past ITB runs (like a chat app's sidebar).
 * Static on desktop; an off-canvas drawer on small screens. Each entry can be
 * renamed inline and deleted (with a confirm step).
 */
export default function HistorySidebar({
  items,
  activeId,
  loading,
  open,
  running,
  onClose,
  onNew,
  onSelect,
  onDelete,
  onRename,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus the rename input as soon as it appears.
  useEffect(() => {
    if (editingId) inputRef.current?.select();
  }, [editingId]);

  /** Enter rename mode for an entry. */
  const startEdit = (item: HistoryItem) => {
    setConfirmId(null);
    setEditingId(item.id);
    setDraft(item.title);
  };

  /** Save the pending rename (if non-empty) and leave edit mode. */
  const commitEdit = () => {
    const value = draft.trim();
    if (editingId && value) onRename(editingId, value);
    setEditingId(null);
  };

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-space-950/70 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={[
          "z-40 flex w-72 shrink-0 flex-col border-r border-ink-800/80 bg-ink-950/55 backdrop-blur-xl",
          "fixed inset-y-0 left-0 transition-transform duration-200",
          "md:sticky md:top-0 md:h-screen md:self-start md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
      >
        <div className="flex items-center justify-between border-b border-ink-800 px-4 py-4">
          <div className="flex items-center gap-2 font-mono text-sm">
            <span className="text-amber">▮</span>
            <span className="font-semibold tracking-tight text-paper-50">automate</span>
          </div>
          <button
            onClick={onClose}
            className="font-mono text-xs text-paper-200/50 hover:text-paper-50 md:hidden"
          >
            close
          </button>
        </div>

        <div className="p-3">
          <button
            onClick={onNew}
            disabled={running}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-ink-700 bg-ink-800 px-3 py-2 font-mono text-xs font-semibold text-paper-50 transition hover:border-amber/50 hover:text-amber disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span className="text-amber">+</span> New ITB
          </button>
        </div>

        <p className="px-4 pb-2 pt-1 font-mono text-[11px] uppercase tracking-wide text-paper-200/40">
          history
        </p>

        <nav className="flex-1 overflow-y-auto px-2 pb-4 scrollbar-thin">
          {loading && items.length === 0 ? (
            <p className="px-3 py-4 font-mono text-xs text-paper-200/40">loading…</p>
          ) : items.length === 0 ? (
            <p className="px-3 py-4 font-mono text-xs leading-relaxed text-paper-200/40">
              No saved ITB runs yet.
              <br />
              Finished runs appear here.
            </p>
          ) : (
            <ul className="space-y-1">
              {items.map((item) => {
                const active = item.id === activeId;
                const editing = editingId === item.id;
                const confirming = confirmId === item.id;

                if (editing) {
                  return (
                    <li key={item.id}>
                      <div className="rounded-lg border border-amber/40 bg-amber/10 p-2">
                        <input
                          ref={inputRef}
                          value={draft}
                          onChange={(e) => setDraft(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") commitEdit();
                            if (e.key === "Escape") setEditingId(null);
                          }}
                          onBlur={commitEdit}
                          className="w-full rounded border border-ink-700 bg-ink-900 px-2 py-1.5 font-mono text-xs text-paper-50 focus:border-amber focus:outline-none"
                        />
                        <div className="mt-1.5 flex justify-end gap-2">
                          <button
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => setEditingId(null)}
                            className="font-mono text-[10px] text-paper-200/50 hover:text-paper-50"
                          >
                            cancel
                          </button>
                          <button
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={commitEdit}
                            className="font-mono text-[10px] text-amber hover:text-amber-light"
                          >
                            save
                          </button>
                        </div>
                      </div>
                    </li>
                  );
                }

                if (confirming) {
                  return (
                    <li key={item.id}>
                      <div className="rounded-lg border border-danger/40 bg-danger/10 p-2.5">
                        <p className="truncate font-mono text-[11px] text-paper-200/80">
                          Delete “{item.title}”?
                        </p>
                        <div className="mt-1.5 flex justify-end gap-2">
                          <button
                            onClick={() => setConfirmId(null)}
                            className="font-mono text-[10px] text-paper-200/50 hover:text-paper-50"
                          >
                            cancel
                          </button>
                          <button
                            onClick={() => {
                              setConfirmId(null);
                              onDelete(item.id);
                            }}
                            className="font-mono text-[10px] text-danger hover:text-danger/80"
                          >
                            delete
                          </button>
                        </div>
                      </div>
                    </li>
                  );
                }

                return (
                  <li key={item.id} className="group relative">
                    <button
                      onClick={() => onSelect(item.id)}
                      className={[
                        "w-full rounded-lg border px-3 py-2.5 pr-14 text-left transition",
                        active
                          ? "border-amber/40 bg-amber/10"
                          : "border-transparent hover:border-ink-700 hover:bg-ink-900",
                      ].join(" ")}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={[
                            "h-1.5 w-1.5 shrink-0 rounded-full",
                            DOT[item.status] ?? DOT.queued,
                          ].join(" ")}
                        />
                        <span className="min-w-0 flex-1 truncate font-mono text-xs font-medium text-paper-50">
                          {item.title}
                        </span>
                        <span className="shrink-0 font-mono text-[10px] text-paper-200/40">
                          {formatWhen(item.created_at)}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center justify-between gap-2 pl-3.5">
                        <span className="min-w-0 truncate font-mono text-[10px] text-paper-200/45">
                          {item.subtitle}
                        </span>
                        <span className="shrink-0 font-mono text-[10px] text-paper-200/45">
                          {item.line_items_count} item{item.line_items_count === 1 ? "" : "s"}
                        </span>
                      </div>
                    </button>

                    <div className="absolute right-1.5 top-1.5 hidden items-center gap-0.5 group-hover:flex">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          startEdit(item);
                        }}
                        title="Rename"
                        className="flex h-6 w-6 items-center justify-center rounded text-paper-200/40 transition hover:bg-ink-800 hover:text-amber"
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M12 20h9" />
                          <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
                        </svg>
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingId(null);
                          setConfirmId(item.id);
                        }}
                        title="Delete"
                        className="flex h-6 w-6 items-center justify-center rounded font-mono text-sm text-paper-200/40 transition hover:bg-danger/10 hover:text-danger"
                      >
                        ×
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </nav>

        <div className="border-t border-ink-800 px-4 py-3 font-mono text-[10px] text-paper-200/30">
          {items.length} saved run{items.length === 1 ? "" : "s"}
        </div>
      </aside>
    </>
  );
}
