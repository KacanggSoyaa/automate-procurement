import { useState } from "react";
import type { RfqEmail } from "../types";

/** Copy text to the clipboard, falling back to a hidden textarea if needed. */
async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    document.body.removeChild(area);
    return ok;
  }
}

/**
 * Section listing copy-ready RFQ emails (one per line item) with a per-email
 * and a "copy all" button.
 */
export default function RfqEmails({ emails }: { emails: RfqEmail[] }) {
  const [copied, setCopied] = useState<string | null>(null);

  /** Copy the given text and briefly flash the "copied" state on that button. */
  const handleCopy = async (key: string, text: string) => {
    const ok = await copyText(text);
    setCopied(ok ? key : null);
    if (ok) {
      window.setTimeout(() => setCopied((current) => (current === key ? null : current)), 1500);
    }
  };

  if (emails.length === 0) {
    return (
      <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-4 font-mono text-xs text-paper-200/40">
        No line items found — no quotation email to generate.
      </div>
    );
  }

  const copyAll = emails.map((e) => `${e.subject}\n\n${e.body}`).join("\n\n---\n\n");
  const isSingle = emails.length === 1;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="font-mono text-xs uppercase tracking-wide text-paper-200/50">
          {isSingle ? "quotation email" : `quotation emails · ${emails.length}`}
        </p>
        {!isSingle && (
          <button
            onClick={() => handleCopy("all", copyAll)}
            className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-1.5 font-mono text-xs text-paper-200/70 transition hover:border-amber/50 hover:text-paper-50"
          >
            {copied === "all" ? "copied" : "copy all"}
          </button>
        )}
      </div>

      {emails.map((email, i) => (
        <div key={i} className="rounded-xl border border-ink-700 bg-ink-900/70 p-4">
          <div className="flex items-center justify-between gap-4">
            <p className="min-w-0 font-mono text-xs text-paper-200/50">
              <span className="text-paper-200/40">SUBJECT: </span>
              <span className="text-amber">{email.subject}</span>
            </p>
            <button
              onClick={() => handleCopy(String(i), `${email.subject}\n\n${email.body}`)}
              className="shrink-0 rounded-lg border border-ink-700 bg-ink-800 px-3 py-1.5 font-mono text-xs text-paper-200/70 transition hover:border-amber/50 hover:text-paper-50"
            >
              {copied === String(i) ? "copied" : "copy email"}
            </button>
          </div>

          <pre className="mt-3 whitespace-pre-wrap break-words rounded-lg border border-ink-800 bg-ink-950/60 p-3 font-mono text-xs leading-relaxed text-paper-200/80">
            {email.body}
          </pre>
        </div>
      ))}
    </div>
  );
}
