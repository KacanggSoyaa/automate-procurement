import { useEffect, useState } from "react";
import Icon from "./Icon";

function clockText(now: Date): string {
  const parts = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).formatToParts(now);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === type)?.value ?? "";
  return `${part("month").toUpperCase()} ${part("day")} · ${part("hour")}:${part("minute")}:${part("second")} ${part("dayPeriod").toUpperCase()}`.trim();
}

function clockTitle(now: Date): string {
  const date = new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(now);
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || "local time";
  return `${date} · ${zone}`;
}

export default function LiveClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <span className="hidden items-center gap-1.5 sm:flex" title={clockTitle(now)}>
      <Icon name="clock" size={12} className="text-amber/70" />
      <span className="tabular-nums text-paper-200/60">{clockText(now)}</span>
      <span className="text-paper-200/25">·</span>
    </span>
  );
}
