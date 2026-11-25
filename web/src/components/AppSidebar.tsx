import { useEffect, useRef, useState } from "react";
import Icon, { type IconName } from "./Icon";
import type { HistoryItem, TabId } from "../types";

export interface NavTab {
  id: TabId;
  label: string;
  icon: IconName;
}

interface Props {
  navTabs: NavTab[];
  activeTab: TabId;
  onTabChange: (id: TabId) => void;
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

const DOT: Record<string, string> = {
  done: "bg-teal",
  error: "bg-danger",
  running: "bg-amber animate-pulse-dot",
  queued: "bg-paper-200/40",
};

const STORAGE_KEY = "automate.sidebar.collapsed";

function navClass(active: boolean, compact: boolean): string {
  return [
    "group flex items-center rounded-lg border font-mono text-xs transition",
    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber/70",
    compact ? "h-10 w-10 justify-center" : "w-full gap-3 px-3 py-2.5 text-left",
    active
      ? "border-amber/30 bg-amber/10 text-amber"
      : "border-transparent text-paper-200/60 hover:bg-ink-900 hover:text-paper-50",
  ].join(" ");
}

export default function AppSidebar({
  navTabs,
  activeTab,
  onTabChange,
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
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return typeof window !== "undefined" && window.localStorage.getItem(STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId) inputRef.current?.select();
  }, [editingId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, String(collapsed));
    } catch {
      return;
    }
  }, [collapsed]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const startEdit = (item: HistoryItem) => {
    setConfirmId(null);
    setEditingId(item.id);
    setDraft(item.title);
  };

  const commitEdit = () => {
    const value = draft.trim();
    if (editingId && value) onRename(editingId, value);
    setEditingId(null);
  };

  const selectTab = (id: TabId) => {
    onTabChange(id);
    onClose();
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
          "z-40 flex shrink-0 flex-col overflow-hidden border-r border-ink-800/80 bg-ink-950/60 backdrop-blur-xl",
          "fixed inset-y-0 left-0 w-72 transition-[width,transform] duration-200",
          "md:sticky md:top-0 md:h-screen md:self-start md:translate-x-0",
          collapsed ? "md:w-[76px]" : "md:w-72",
          open ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
      >
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-ink-800 px-3 md:px-4">
          <div className="flex items-center gap-2 font-mono text-sm">
            <span className="text-amber">▮</span>
            <span
              className={[
                "font-semibold tracking-tight text-paper-50",
                collapsed ? "md:hidden" : "",
              ].join(" ")}
            >
              automate
            </span>
          </div>
          <button
            onClick={() => setCollapsed((v) => !v)}
            title={collapsed ? "Expand navigation" : "Collapse navigation"}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
            aria-expanded={!collapsed}
            className="hidden h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-paper-200/50 transition hover:border-amber/50 hover:text-amber focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber/70 md:flex"
          >
            <Icon name={collapsed ? "chevronRight" : "chevronLeft"} size={15} />
          </button>
          <button
            onClick={onClose}
            title="Close navigation"
            aria-label="Close navigation"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-paper-200/50 transition hover:border-amber/50 hover:text-amber focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber/70 md:hidden"
          >
            <Icon name="close" size={15} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain scrollbar-thin">
          <div className={collapsed ? "md:hidden" : ""}>
            <div className="px-2 pt-4">
              <p className="mb-2 px-2 font-mono text-[10px] uppercase tracking-[0.22em] text-paper-200/35">
                workspace
              </p>
              <ul className="space-y-1">
                {navTabs.map((tab) => {
                  const active = tab.id === activeTab;
                  return (
                    <li key={tab.id}>
                      <button
                        onClick={() => selectTab(tab.id)}
                        aria-current={active ? "page" : undefined}
                        className={navClass(active, false)}
                      >
                        <span
                          className={
                            active
                              ? "text-amber"
                              : "text-paper-200/40 transition group-hover:text-paper-200/80"
                          }
                        >
                          <Icon name={tab.icon} size={16} />
                        </span>
                        <span className="truncate">{tab.label}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="mt-4 border-t border-ink-800/80 px-3 pt-4">
              <button
                onClick={onNew}
                disabled={running}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-ink-700 bg-ink-800 px-3 py-2 font-mono text-xs font-semibold text-paper-50 transition hover:border-amber/50 hover:text-amber focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber/70 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Icon name="plus" size={14} className="text-amber" />
                New ITB
              </button>
            </div>

            <p className="px-4 pb-2 pt-5 font-mono text-[10px] uppercase tracking-[0.22em] text-paper-200/35">
              history
            </p>

            <nav className="px-2 pb-4">
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
                            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber/70",
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

                        <div className="absolute right-1.5 top-1.5 hidden items-center gap-0.5 group-hover:flex group-focus-within:flex">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              startEdit(item);
                            }}
                            title="Rename"
                            aria-label={`Rename ${item.title}`}
                            className="flex h-6 w-6 items-center justify-center rounded text-paper-200/40 transition hover:bg-ink-800 hover:text-amber focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber/70"
                          >
                            <Icon name="pencil" size={12} />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingId(null);
                              setConfirmId(item.id);
                            }}
                            title="Delete"
                            aria-label={`Delete ${item.title}`}
                            className="flex h-6 w-6 items-center justify-center rounded text-paper-200/40 transition hover:bg-danger/10 hover:text-danger focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber/70"
                          >
                            <Icon name="close" size={12} />
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
          </div>

          {collapsed && (
            <div className="hidden md:block">
              <div className="flex flex-col items-center gap-1 px-2 pt-4">
                {navTabs.map((tab) => {
                  const active = tab.id === activeTab;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => selectTab(tab.id)}
                      title={tab.label}
                      aria-label={tab.label}
                      aria-current={active ? "page" : undefined}
                      className={navClass(active, true)}
                    >
                      <Icon name={tab.icon} size={16} />
                    </button>
                  );
                })}
              </div>

              <div className="mt-4 flex flex-col items-center gap-3 border-t border-ink-800/80 px-2 pt-4">
                <button
                  onClick={onNew}
                  disabled={running}
                  title="New ITB"
                  aria-label="New ITB"
                  className="flex h-10 w-10 items-center justify-center rounded-lg border border-ink-700 bg-ink-800 text-amber transition hover:border-amber/50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber/70 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Icon name="plus" size={15} />
                </button>

                {loading && items.length === 0 ? (
                  <span className="h-2 w-2 animate-pulse-dot rounded-full bg-paper-200/40" />
                ) : (
                  <ul className="flex flex-col items-center gap-1">
                    {items.map((item) => (
                      <li key={item.id}>
                        <button
                          onClick={() => onSelect(item.id)}
                          title={`${item.title} · ${item.status}`}
                          aria-label={`Open ${item.title}`}
                          className={[
                            "flex h-8 w-8 items-center justify-center rounded-lg border transition",
                            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber/70",
                            item.id === activeId
                              ? "border-amber/40 bg-amber/10"
                              : "border-transparent hover:border-ink-700 hover:bg-ink-900",
                          ].join(" ")}
                        >
                          <span
                            className={[
                              "h-2 w-2 rounded-full",
                              DOT[item.status] ?? DOT.queued,
                            ].join(" ")}
                          />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div
                className="mt-4 border-t border-ink-800 py-3 text-center font-mono text-[10px] text-paper-200/30"
                title={`${items.length} saved runs`}
              >
                {items.length}
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
