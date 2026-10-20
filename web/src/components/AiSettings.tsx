import { useEffect, useState } from "react";
import { getAiSettings, updateAiSettings } from "../api";
import type { AiSettings as AiSettingsType } from "../types";

/**
 * Settings section where a user stores their own Gemini API key and picks the
 * model used for their runs. The key is saved server-side and only ever shown
 * back as a masked hint; a separate Clear button removes it. When no personal
 * key is set the server's shared key (if any) is used instead.
 */
export default function AiSettings({ onError }: { onError: (msg: string) => void }) {
  const [settings, setSettings] = useState<AiSettingsType | null>(null);
  const [loading, setLoading] = useState(true);
  const [keyInput, setKeyInput] = useState("");
  const [model, setModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = async () => {
    try {
      const s = await getAiSettings();
      setSettings(s);
      setModel(s.model ?? "");
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const flash = (msg: string) => {
    setNotice(msg);
    window.setTimeout(() => setNotice((c) => (c === msg ? null : c)), 2500);
  };

  const saveKey = async () => {
    if (keyInput.trim().length < 10) {
      onError("That API key looks too short.");
      return;
    }
    setSaving(true);
    try {
      const s = await updateAiSettings({ apiKey: keyInput.trim() });
      setSettings((prev) => ({ ...(prev ?? s), ...s }));
      setKeyInput("");
      flash("api key saved");
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const clearKey = async () => {
    setSaving(true);
    try {
      const s = await updateAiSettings({ clearKey: true });
      setSettings((prev) => ({ ...(prev ?? s), ...s }));
      flash("api key removed");
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const saveModel = async () => {
    setSaving(true);
    try {
      const s = await updateAiSettings({ model: model.trim() });
      setSettings((prev) => ({ ...(prev ?? s), ...s }));
      flash(model.trim() ? "model saved" : "using default model");
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const defaultModel = settings?.default_model ?? "gemini-3.8-flash";
  const modelChoices = [defaultModel, ...(settings?.fallback_models ?? [])];

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-ink-700 bg-ink-900/70 p-5">
        <div className="flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">
            gemini api key
          </p>
          {settings?.has_api_key ? (
            <span className="font-mono text-[11px] text-teal">saved {settings.api_key_hint}</span>
          ) : (
            <span className="font-mono text-[11px] text-paper-200/40">not set</span>
          )}
        </div>

        <p className="mt-2 font-sans text-xs leading-relaxed text-paper-200/50">
          Your key is stored on the server for your account only and never sent back to the browser
          — you will only ever see a masked hint. {settings?.env_key_available
            ? "If you leave this empty, the server's shared key is used."
            : "No shared server key is configured, so a personal key is required to run the pipeline."}
        </p>

        {loading ? (
          <p className="mt-3 font-mono text-xs text-paper-200/40">loading…</p>
        ) : (
          <>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                type="password"
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                disabled={saving}
                autoComplete="off"
                placeholder={settings?.has_api_key ? "paste a new key to replace…" : "AIza…"}
                className="min-w-[240px] flex-1 rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 font-mono text-xs text-paper-50 placeholder:text-paper-200/30 focus:border-amber focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
              />
              <button
                onClick={saveKey}
                disabled={saving || keyInput.trim().length === 0}
                className="rounded-lg bg-amber px-4 py-2 font-mono text-xs font-semibold text-space-950 transition hover:bg-amber-light disabled:cursor-not-allowed disabled:opacity-50"
              >
                {settings?.has_api_key ? "REPLACE" : "SAVE"}
              </button>
              {settings?.has_api_key && (
                <button
                  onClick={clearKey}
                  disabled={saving}
                  className="rounded-lg border border-ink-700 px-4 py-2 font-mono text-xs text-paper-200/70 transition hover:border-danger/50 hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
                >
                  CLEAR
                </button>
              )}
            </div>
            <a
              href="https://aistudio.google.com/apikey"
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-block font-mono text-[11px] text-paper-200/40 underline decoration-dotted transition hover:text-paper-100"
            >
              get a Gemini API key ↗
            </a>
          </>
        )}
      </div>

      <div className="rounded-2xl border border-ink-700 bg-ink-900/70 p-5">
        <div className="flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">model</p>
          <span className="font-mono text-[11px] text-paper-200/40">
            {model.trim() || "default"}
          </span>
        </div>

        <p className="mt-2 font-sans text-xs leading-relaxed text-paper-200/50">
          Which Gemini model reads your ITB. Leave on the default unless you have a reason to
          change it; the backend also falls back to other models if this one is busy.
        </p>

        {!loading && (
          <>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                list="gemini-models"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={saving}
                placeholder={defaultModel}
                className="min-w-[240px] flex-1 rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 font-mono text-xs text-paper-50 placeholder:text-paper-200/30 focus:border-amber focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
              />
              <datalist id="gemini-models">
                {modelChoices.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
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
          </>
        )}
      </div>

      {notice && (
        <p className="font-mono text-xs text-teal">{notice}</p>
      )}
    </div>
  );
}
