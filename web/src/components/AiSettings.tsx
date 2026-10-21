import { useEffect, useState } from "react";
import { getAiSettings, updateAiSettings } from "../api";
import type { AiProviderInfo, AiSettings as AiSettingsType } from "../types";

/**
 * Settings section where a user picks the AI provider (Gemini, OpenAI or
 * Anthropic), stores that provider's API key and picks the model used for
 * their runs. Keys are saved server-side and only ever shown back as a masked
 * hint; a separate Clear button removes them. A final toggle decides whether
 * supplier search also runs on the chosen provider or stays on Gemini.
 */
export default function AiSettings({ onError }: { onError: (msg: string) => void }) {
  const [settings, setSettings] = useState<AiSettingsType | null>(null);
  const [loading, setLoading] = useState(true);
  const [keyInput, setKeyInput] = useState("");
  const [model, setModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const active: AiProviderInfo | undefined =
    settings?.providers?.find((p) => p.id === settings?.provider) ?? settings?.providers?.[0];

  const load = async () => {
    try {
      const s = await getAiSettings();
      apply(s);
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  /** Store a fresh payload and sync the model field with the active provider. */
  const apply = (s: AiSettingsType) => {
    setSettings(s);
    const info = s.providers?.find((p) => p.id === s.provider) ?? s.providers?.[0];
    setModel(info?.model ?? "");
    setKeyInput("");
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const flash = (msg: string) => {
    setNotice(msg);
    window.setTimeout(() => setNotice((c) => (c === msg ? null : c)), 2500);
  };

  const save = async (
    input: Parameters<typeof updateAiSettings>[0],
    flashMsg?: string,
  ) => {
    setSaving(true);
    try {
      const s = await updateAiSettings(input);
      apply(s);
      if (flashMsg) flash(flashMsg);
      return s;
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setSaving(false);
    }
  };

  const saveKey = async () => {
    if (keyInput.trim().length < 10) {
      onError("That API key looks too short.");
      return;
    }
    await save({ provider: active?.id, apiKey: keyInput.trim() }, "api key saved");
  };

  const clearKey = async () => {
    await save({ provider: active?.id, clearKey: true }, "api key removed");
  };

  const saveModel = async () => {
    const m = model.trim();
    await save({ provider: active?.id, model: m }, m ? "model saved" : "using default model");
  };

  const changeProvider = async (pid: string) => {
    const info = settings?.providers?.find((p) => p.id === pid);
    await save({ provider: pid }, `${info?.label ?? pid} selected`);
  };

  const toggleSupplierSearch = async (enabled: boolean) => {
    await save(
      { supplierSearchProvider: enabled },
      enabled
        ? "supplier search follows your provider"
        : "supplier search stays on Gemini",
    );
  };

  if (loading || !settings || !active) {
    return <p className="font-mono text-xs text-paper-200/40">loading…</p>;
  }

  const defaultModel = active.default_model;
  const modelChoices = [...new Set([defaultModel, ...active.models, model.trim()].filter(Boolean))];
  const supplierSearchOn = settings.supplier_search_provider !== false;
  const usesGemini = active.id === "gemini";

  return (
    <div className="space-y-5">
      {/* ── provider ─────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-ink-700 bg-ink-900/70 p-5">
        <div className="flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">
            ai provider
          </p>
          <span className="font-mono text-[11px] text-paper-200/40">
            {active.model ?? `default (${defaultModel})`}
          </span>
        </div>

        <p className="mt-2 font-sans text-xs leading-relaxed text-paper-200/50">
          Which AI reads your ITBs and searches suppliers: Google Gemini, OpenAI or Anthropic.
          Each provider keeps its own API key and model below.
        </p>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select
            value={active.id}
            onChange={(e) => changeProvider(e.target.value)}
            disabled={saving}
            className="min-w-[240px] flex-1 rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 font-mono text-xs text-paper-50 focus:border-amber focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          >
            {settings.providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ── API key for the selected provider ────────────────────── */}
      <div className="rounded-2xl border border-ink-700 bg-ink-900/70 p-5">
        <div className="flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">
            {active.id} api key
          </p>
          {active.has_api_key ? (
            <span className="font-mono text-[11px] text-teal">saved {active.api_key_hint}</span>
          ) : (
            <span className="font-mono text-[11px] text-paper-200/40">not set</span>
          )}
        </div>

        <p className="mt-2 font-sans text-xs leading-relaxed text-paper-200/50">
          Your {active.label} key is stored on the server for your account only and never sent
          back to the browser — you will only ever see a masked hint.{" "}
          {active.env_key_available
            ? "If you leave this empty, the server's shared key is used."
            : `No shared server key is configured for ${active.env_key ?? active.id}, so a personal key is required.`}
        </p>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            disabled={saving}
            autoComplete="off"
            placeholder={active.has_api_key ? "paste a new key to replace…" : "API key…"}
            className="min-w-[240px] flex-1 rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 font-mono text-xs text-paper-50 placeholder:text-paper-200/30 focus:border-amber focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          />
          <button
            onClick={saveKey}
            disabled={saving || keyInput.trim().length === 0}
            className="rounded-lg bg-amber px-4 py-2 font-mono text-xs font-semibold text-space-950 transition hover:bg-amber-light disabled:cursor-not-allowed disabled:opacity-50"
          >
            {active.has_api_key ? "REPLACE" : "SAVE"}
          </button>
          {active.has_api_key && (
            <button
              onClick={clearKey}
              disabled={saving}
              className="rounded-lg border border-ink-700 px-4 py-2 font-mono text-xs text-paper-200/70 transition hover:border-danger/50 hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
            >
              CLEAR
            </button>
          )}
        </div>
        {active.key_url && (
          <a
            href={active.key_url}
            target="_blank"
            rel="noreferrer"
            className="mt-2 inline-block font-mono text-[11px] text-paper-200/40 underline decoration-dotted transition hover:text-paper-100"
          >
            get an {active.label} API key ↗
          </a>
        )}
      </div>

      {/* ── model for the selected provider ──────────────────────── */}
      <div className="rounded-2xl border border-ink-700 bg-ink-900/70 p-5">
        <div className="flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">model</p>
          <span className="font-mono text-[11px] text-paper-200/40">
            {model.trim() || "default"}
          </span>
        </div>

        <p className="mt-2 font-sans text-xs leading-relaxed text-paper-200/50">
          Which {active.label} model reads your ITB. Leave on the default unless you have a
          reason to change it; the backend also falls back to other models if this one is busy.
        </p>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select
            value={model.trim()}
            onChange={(e) => setModel(e.target.value)}
            disabled={saving}
            className="min-w-[240px] flex-1 rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 font-mono text-xs text-paper-50 focus:border-amber focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="">default ({defaultModel})</option>
            {modelChoices.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <button
            onClick={saveModel}
            disabled={saving}
            className="rounded-lg border border-ink-700 px-4 py-2 font-mono text-xs text-paper-200/70 transition hover:border-amber/50 hover:text-paper-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            SAVE
          </button>
        </div>
        <p className="mt-2 font-mono text-[11px] text-paper-200/40">
          empty = use the default ({defaultModel})
        </p>
      </div>

      {/* ── supplier search target ───────────────────────────────── */}
      <div className="rounded-2xl border border-ink-700 bg-ink-900/70 p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">
              supplier search
            </p>
            <p className="mt-2 font-sans text-xs leading-relaxed text-paper-200/50">
              {supplierSearchOn
                ? `Supplier shortlisting also runs on ${active.label}, using its live web search and your key above.`
                : "Supplier shortlisting stays on Google Gemini; your provider is only used for document classification."}
            </p>
          </div>
          <button
            role="switch"
            aria-checked={supplierSearchOn}
            onClick={() => toggleSupplierSearch(!supplierSearchOn)}
            disabled={saving}
            className={`h-5 w-9 shrink-0 rounded-full border transition disabled:cursor-not-allowed disabled:opacity-50 ${
              supplierSearchOn ? "border-teal bg-teal/30" : "border-ink-700 bg-ink-900"
            }`}
          >
            <span
              className={`block h-3.5 w-3.5 rounded-full transition ${
                supplierSearchOn ? "translate-x-4 bg-teal" : "translate-x-0.5 bg-paper-200/40"
              }`}
            />
          </button>
        </div>
        {!usesGemini && !supplierSearchOn && (
          <p className="mt-2 font-mono text-[11px] text-amber/80">
            supplier search needs the shared Gemini key ({settings.providers.find((p) => p.id === "gemini")?.env_key ?? "GEMINI_API_KEY"})
          </p>
        )}
      </div>

      {notice && (
        <p className="font-mono text-xs text-teal">{notice}</p>
      )}
    </div>
  );
}
