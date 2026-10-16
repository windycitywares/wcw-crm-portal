import { Pill, type Tone } from "./Pill";

export const TONES: Tone[] = ["neutral", "accent", "success", "warning", "danger", "info"];
const TONE_LABEL: Record<Tone, string> = {
  neutral: "Grey",
  accent: "Blue",
  success: "Green",
  warning: "Amber",
  danger: "Red",
  info: "Sky",
};

/** Options for a colour <select>: theme tones only, so colours stay readable in every theme. */
export const COLOR_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "No colour" },
  ...TONES.map((t) => ({ value: t, label: TONE_LABEL[t] })),
];

/**
 * A label with its colour: a theme tone (e.g. "success") or a #rrggbb set through the API.
 * The text always carries the meaning; colour is only a hint.
 */
export function ColorTag({ color, children, className }: { color?: string | null; children: React.ReactNode; className?: string }) {
  if (!color || (TONES as string[]).includes(color)) {
    return (
      <Pill tone={(color || "neutral") as Tone} className={className}>
        {children}
      </Pill>
    );
  }
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-0.5 text-xs font-medium ${className ?? ""}`}>
      <span aria-hidden="true" className="size-1.5 rounded-full" style={{ background: color }} />
      {children}
    </span>
  );
}
