import { useState } from "react";
import type { AuthUser, Job } from "../types";
import Icon, { type IconName } from "./Icon";
import QuickSupplierSearch from "./QuickSupplierSearch";
import SupplierDirectory from "./SupplierDirectory";
import SupplierPanel from "./SupplierPanel";

type SupplierView = "directory" | "search" | "byname";

interface Props {
  job: Job | null;
  user: AuthUser;
  needsSetup: boolean;
  onError: (message: string) => void;
  onUpdated: (job: Job) => void;
  onOpenSettings: () => void;
  onViewChange?: () => void;
}

const VIEWS: { id: SupplierView; label: string; icon: IconName }[] = [
  { id: "directory", label: "supplier list", icon: "directory" },
  { id: "search", label: "project search", icon: "suppliers" },
  { id: "byname", label: "by name", icon: "quicksearch" },
];

export default function SupplierWorkspace({
  job,
  user,
  needsSetup,
  onError,
  onUpdated,
  onOpenSettings,
  onViewChange,
}: Props) {
  const [view, setView] = useState<SupplierView>("directory");
  const done = job?.status === "done";

  const selectView = (next: SupplierView) => {
    setView(next);
    onViewChange?.();
  };

  return (
    <section>
      <section className="pb-8 pt-6">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber/80">
          Workspace — Suppliers
        </p>
        <h1 className="mt-3 font-mono text-3xl font-semibold leading-tight text-paper-50 sm:text-4xl">
          Every supplier, one place.
        </h1>
        <p className="mt-4 max-w-2xl font-sans text-sm leading-relaxed text-paper-200/70">
          Keep your master list, shortlist suppliers for the current project, and search by item
          name — all in the same workspace.
        </p>
      </section>

      <div
        role="tablist"
        aria-label="Supplier views"
        className="mb-7 flex gap-1 overflow-x-auto rounded-xl border border-ink-800 bg-ink-950/50 p-1"
      >
        {VIEWS.map((item) => {
          const active = view === item.id;
          return (
            <button
              key={item.id}
              role="tab"
              aria-selected={active}
              onClick={() => selectView(item.id)}
              className={[
                "flex shrink-0 items-center gap-2 rounded-lg px-4 py-2 font-mono text-xs uppercase tracking-wider transition",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber/70",
                active
                  ? "bg-amber/10 text-amber"
                  : "text-paper-200/50 hover:bg-ink-900 hover:text-paper-50",
              ].join(" ")}
            >
              <Icon name={item.icon} size={15} />
              {item.label}
            </button>
          );
        })}
      </div>

      {view === "directory" && (
        <div role="tabpanel" className="space-y-5">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber/70">Master list</p>
            <h2 className="mt-2 font-mono text-2xl font-semibold text-paper-50 sm:text-3xl">
              Your supplier directory.
            </h2>
            <p className="mt-3 max-w-2xl font-sans text-sm leading-relaxed text-paper-200/70">
              Add suppliers by hand or import a run's shortlist. This list is saved on the server
              and stays available for every future ITB.
            </p>
          </div>
          <SupplierDirectory job={job} user={user} onError={onError} />
        </div>
      )}

      {view === "search" && (
        <div role="tabpanel" className="space-y-5">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber/70">Current project</p>
            <h2 className="mt-2 font-mono text-2xl font-semibold text-paper-50 sm:text-3xl">
              Shortlist suppliers.
            </h2>
            <p className="mt-3 max-w-2xl font-sans text-sm leading-relaxed text-paper-200/70">
              Run a live web search per line item, or use one shared list for everything. Export
              the shortlist as a CSV when you are done.
            </p>
          </div>

          {needsSetup && (
            <div className="rounded-xl border border-amber/30 bg-amber/5 p-4 font-mono text-xs text-amber/80">
              You can review this project's suppliers now. Add your API key in{" "}
              <button
                onClick={onOpenSettings}
                className="underline decoration-amber/40 underline-offset-2 hover:text-amber"
              >
                settings
              </button>{" "}
              to run new searches.
            </div>
          )}

          {done && job ? (
            <SupplierPanel job={job} onError={onError} onUpdated={onUpdated} />
          ) : (
            <div className="rounded-2xl border border-dashed border-ink-700 bg-ink-900/40 p-8 text-center">
              <p className="font-mono text-xs text-paper-200/50">
                This project's pipeline must be finished before supplier search unlocks.
              </p>
            </div>
          )}
        </div>
      )}

      {view === "byname" && (
        <div role="tabpanel" className="space-y-5">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber/70">Standalone</p>
            <h2 className="mt-2 font-mono text-2xl font-semibold text-paper-50 sm:text-3xl">
              Find suppliers by item name.
            </h2>
            <p className="mt-3 max-w-2xl font-sans text-sm leading-relaxed text-paper-200/70">
              Enter only an item name and get suppliers with websites, contacts and emails. Save
              any result straight to your directory.
            </p>
          </div>
          <QuickSupplierSearch onError={onError} />
        </div>
      )}
    </section>
  );
}
