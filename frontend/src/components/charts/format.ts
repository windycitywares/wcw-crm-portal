/** Number, money and date formatting shared by the admin charts, tables and tiles. */

const US = "en-US";

let zone: string | undefined;
/** The store's time zone (Settings → General): the admin shows clock times in it, whatever the browser's zone is. */
export function setStoreTimeZone(name: string | undefined): void {
  zone = name;
}
export function storeTimeZone(): string | undefined {
  return zone;
}
const int = new Intl.NumberFormat(US, { maximumFractionDigits: 0 });
const one = new Intl.NumberFormat(US, { maximumFractionDigits: 1 });
const usd = new Intl.NumberFormat(US, { style: "currency", currency: "USD" });
const usd0 = new Intl.NumberFormat(US, { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const fmtInt = (n: number) => int.format(n);

/** 1,284 / 12.9K / 4.2M — for axis ticks and big tiles. */
export function compact(n: number): string {
  const a = Math.abs(n);
  if (a >= 1e9) return `${one.format(n / 1e9)}B`;
  if (a >= 1e6) return `${one.format(n / 1e6)}M`;
  if (a >= 1e4) return `${one.format(n / 1e3)}K`;
  return int.format(n);
}

export function money(n: number, opts: { compact?: boolean; cents?: boolean } = {}): string {
  if (opts.compact && Math.abs(n) >= 10_000) return `$${compact(n)}`;
  if (opts.cents === false || (opts.cents === undefined && Math.abs(n) >= 1000)) return usd0.format(n);
  return usd.format(n);
}

/** Fraction → "12.3%". */
export function pct(n: number, digits = 1): string {
  return `${(n * 100).toFixed(digits).replace(/\.0+$/, "")}%`;
}

/** "Oct 14" (short) or "Tue, Oct 14" (long). Input: ISO date or datetime (UTC date part is used). */
export function dayLabel(iso: string, style: "short" | "long" = "short"): string {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso);
  const opts: Intl.DateTimeFormatOptions =
    style === "long" ? { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" } : { month: "short", day: "numeric", timeZone: "UTC" };
  return new Intl.DateTimeFormat(US, opts).format(d);
}

export function dateTime(iso: string): string {
  return new Intl.DateTimeFormat(US, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: zone }).format(new Date(iso));
}

export function timeAgo(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} hr ago`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d} day${d === 1 ? "" : "s"} ago`;
  return dayLabel(iso);
}

/** Round, human-friendly axis ticks covering [min, max] (always includes 0 when min ≥ 0). */
export function niceTicks(min: number, max: number, target = 4): number[] {
  if (!isFinite(min) || !isFinite(max)) return [0, 1];
  // A flat or empty series: an all-zero chart gets 0–4 (whole numbers), not 0–1 in quarters.
  if (min === max) max = min === 0 ? 4 : min + Math.abs(min) * 0.2;
  const span = max - min;
  const raw = span / Math.max(1, target);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
  const start = Math.floor(min / step) * step;
  const end = Math.ceil(max / step) * step;
  const out: number[] = [];
  for (let v = start; v <= end + step / 1e6; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}

/** Evenly spaced indices for x-axis labels (always includes first and last). */
export function labelIndices(n: number, maxLabels: number): number[] {
  if (n <= 0) return [];
  if (n <= maxLabels) return Array.from({ length: n }, (_, i) => i);
  const step = (n - 1) / (maxLabels - 1);
  const idx = new Set<number>();
  for (let i = 0; i < maxLabels; i++) idx.add(Math.round(i * step));
  return [...idx];
}

/** Series colour by slot. Single-series charts use the theme accent instead. */
export const seriesColor = (i: number) => `var(--viz-${(i % 8) + 1})`;
