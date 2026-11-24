"use client";

import { useId, useRef } from "react";
import { cn } from "@/lib/utils";
import { TONES } from "./ColorTag";
import { Popover } from "./Popover";
import type { Tone } from "./Pill";

/** Theme tones first (they follow light/dark mode), then fixed colours. Names are what screen readers announce. */
const TONE_SWATCH: Record<Tone, { name: string; className: string }> = {
  neutral: { name: "Grey", className: "bg-muted" },
  accent: { name: "Blue", className: "bg-accent" },
  success: { name: "Green", className: "bg-success" },
  warning: { name: "Amber", className: "bg-warning" },
  danger: { name: "Red", className: "bg-danger" },
  info: { name: "Sky", className: "bg-[var(--viz-1)]" },
};
export const PALETTE: { value: string; name: string }[] = [
  { value: "#7c3aed", name: "Violet" },
  { value: "#4f46e5", name: "Indigo" },
  { value: "#0891b2", name: "Cyan" },
  { value: "#0d9488", name: "Teal" },
  { value: "#65a30d", name: "Lime" },
  { value: "#ea580c", name: "Orange" },
  { value: "#e11d48", name: "Rose" },
  { value: "#db2777", name: "Pink" },
  { value: "#92400e", name: "Brown" },
  { value: "#475569", name: "Slate" },
];

export function colorName(value: string | null | undefined): string {
  if (!value) return "No colour";
  if ((TONES as string[]).includes(value)) return TONE_SWATCH[value as Tone].name;
  return PALETTE.find((p) => p.value.toLowerCase() === value.toLowerCase())?.name ?? value.toUpperCase();
}

/** The dot that stands for a colour (empty ring = no colour). */
export function Swatch({ value, className }: { value: string | null | undefined; className?: string }) {
  const tone = value && (TONES as string[]).includes(value) ? TONE_SWATCH[value as Tone] : null;
  return (
    <span aria-hidden="true"
      className={cn("inline-block size-5 shrink-0 rounded-full ring-1 ring-inset ring-ink/15", tone?.className,
        !value && "bg-[repeating-linear-gradient(135deg,transparent_0_3px,var(--color-line)_3px_4px)]", className)}
      style={value && !tone ? { background: value } : undefined} />
  );
}

/** Pick a colour from swatches: no colour, the theme tones, a set of fixed colours, or any colour ("Custom").
 *  Arrow keys move between swatches; the current one is marked and announced. */
export function ColorPicker({ value, onChange, label = "Colour", disabled, className, hideLabel }: {
  value: string | null | undefined;
  onChange: (value: string) => void;
  label?: string;
  disabled?: boolean;
  className?: string;
  hideLabel?: boolean;
}) {
  const id = useId();
  const box = useRef<HTMLDivElement>(null);
  const current = (value ?? "").toLowerCase();
  const options = [{ value: "", name: "No colour" }, ...TONES.map((t) => ({ value: t as string, name: TONE_SWATCH[t].name })), ...PALETTE];
  const known = options.some((o) => o.value.toLowerCase() === current);
  const custom = current.startsWith("#") && !known ? current : "";

  const onKey = (e: React.KeyboardEvent) => {
    if (!["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(e.key)) return;
    const els = [...(box.current?.querySelectorAll<HTMLElement>("[data-swatch]") ?? [])];
    const i = els.indexOf(document.activeElement as HTMLElement);
    if (i < 0) return;
    e.preventDefault();
    els[(i + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1) + els.length) % els.length]?.focus();
  };

  return (
    <div role="radiogroup" aria-labelledby={`${id}-l`} className={cn("min-w-0", className)}>
      <div id={`${id}-l`} className={cn("mb-1 flex items-center gap-2 text-sm font-semibold text-ink", hideLabel && "sr-only")}>
        {label}<span className="font-normal text-muted">· {colorName(value)}</span>
      </div>
      <div ref={box} onKeyDown={onKey} className="flex flex-wrap items-center gap-1.5">
        {options.map((o) => {
          const on = o.value.toLowerCase() === current;
          return (
            <button key={o.value || "none"} type="button" role="radio" aria-checked={on} data-swatch
              tabIndex={on || (!current && !o.value) || (!known && !custom && !o.value) ? 0 : -1}
              disabled={disabled} title={o.name} onClick={() => onChange(o.value)}
              className={cn("grid size-8 place-items-center rounded-full transition-transform hover:scale-110 disabled:opacity-50",
                on ? "ring-2 ring-ink ring-offset-2 ring-offset-surface" : "")}>
              <Swatch value={o.value} className="size-6" />
              <span className="sr-only">{o.name}</span>
            </button>
          );
        })}
        <label title="Custom colour"
          className={cn("relative grid size-8 cursor-pointer place-items-center rounded-full transition-transform hover:scale-110 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent",
            custom ? "ring-2 ring-ink ring-offset-2 ring-offset-surface" : "", disabled && "pointer-events-none opacity-50")}>
          <span aria-hidden="true" className="size-6 rounded-full ring-1 ring-inset ring-ink/15"
            style={{ background: custom || "conic-gradient(red, yellow, lime, cyan, blue, magenta, red)" }} />
          <span className="sr-only">Custom colour{custom ? ` (${custom})` : ""}</span>
          <input type="color" data-swatch tabIndex={custom ? 0 : -1} disabled={disabled} value={custom || "#888888"}
            onChange={(e) => onChange(e.target.value)} className="absolute inset-0 size-full cursor-pointer opacity-0" />
        </label>
      </div>
    </div>
  );
}

/** A small swatch button that opens the palette — for a colour inside a list row. */
export function ColorButton({ value, onChange, label, disabled }: {
  value: string | null | undefined; onChange: (value: string) => void; label: string; disabled?: boolean;
}) {
  return (
    <Popover label={`${label}: ${colorName(value)}`} align="right"
      triggerClassName={cn("grid size-9 place-items-center p-0 rounded-[var(--radius-control)] border border-line hover:border-ink/40", disabled && "pointer-events-none opacity-50")}
      trigger={<Swatch value={value} />} panelClassName="w-72 p-3">
      {(close) => <ColorPicker label={label} value={value} disabled={disabled} onChange={(v) => { onChange(v); close(); }} />}
    </Popover>
  );
}
