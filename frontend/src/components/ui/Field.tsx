"use client";

import { forwardRef, useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Icon } from "./Icon";

/** One height for every single-line control, so a row of inputs, selects and buttons lines up. */
export const CONTROL_HEIGHT = "h-9";

const control =
  "w-full min-w-0 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm text-ink placeholder:text-muted/70 transition-colors hover:border-ink/40 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/25 disabled:cursor-not-allowed disabled:bg-canvas disabled:text-muted aria-[invalid=true]:border-danger aria-[invalid=true]:focus-visible:border-danger aria-[invalid=true]:focus-visible:ring-danger/20";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, type, pattern, ...props }, ref) {
    // A required text box must hold more than spaces; the browser counts "   " as filled in.
    const textLike = type === undefined || type === "text" || type === "search" || type === "tel";
    const blankGuard = props.required && textLike && !pattern ? { pattern: ".*\\S.*", "data-pattern-message": "Enter more than spaces." } : {};
    const singleLine = type !== "checkbox" && type !== "radio" && type !== "file" && type !== "color" && type !== "range";
    return (
      <input ref={ref} type={type} pattern={pattern} {...blankGuard}
        className={cn(singleLine ? cn(control, CONTROL_HEIGHT, "py-0") : type === "file" ? cn(control, "py-2 file:mr-3 file:rounded file:border-0 file:bg-sand file:px-3 file:py-1 file:text-sm file:font-medium") : "", className)}
        {...props} />
    );
  },
);

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, multiple, ...props }, ref) {
    return <select ref={ref} multiple={multiple} className={cn(control, multiple ? "py-2" : cn(CONTROL_HEIGHT, "py-0 pr-8"), className)} {...props} />;
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return <textarea ref={ref} className={cn(control, "min-h-[100px] py-2 leading-relaxed", className)} {...props} />;
  },
);

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("mb-1 block text-sm font-semibold text-ink", className)} {...props} />;
}

type Control = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

/** A plain-language message for a control that failed the browser's own checks (required, type, min/max, length,
 *  pattern). The browser's wording varies by browser and language, so the common cases are said here. */
export function validityMessage(el: Control, label: string): string {
  const v = el.validity;
  const name = label.replace(/\s*\(.*\)\s*$/, "").toLowerCase();
  if (v.valueMissing) {
    if (el instanceof HTMLSelectElement) return `Choose ${name}.`;
    if (el instanceof HTMLInputElement && (el.type === "checkbox" || el.type === "radio")) return "Tick this to continue.";
    if (el instanceof HTMLInputElement && el.type === "file") return "Choose a file.";
    return `Enter ${name}.`;
  }
  if (v.typeMismatch && el instanceof HTMLInputElement) {
    if (el.type === "email") return el.multiple ? "Enter email addresses separated by commas, like name@example.com." : "Enter an email address like name@example.com.";
    if (el.type === "url") return "Enter a full web address starting with https://.";
  }
  if (v.badInput) return el instanceof HTMLInputElement && el.type === "number" ? "Enter a number." : "Check this value.";
  if (v.tooShort && "minLength" in el) return `Use at least ${el.minLength} characters (now ${el.value.length}).`;
  if (v.tooLong && "maxLength" in el) return `Use at most ${el.maxLength} characters (now ${el.value.length}).`;
  if (v.rangeUnderflow && el instanceof HTMLInputElement) return el.type.startsWith("date") || el.type === "time" ? `Pick ${el.min} or later.` : `Must be ${el.min} or more.`;
  if (v.rangeOverflow && el instanceof HTMLInputElement) return el.type.startsWith("date") || el.type === "time" ? `Pick ${el.max} or earlier.` : `Must be ${el.max} or less.`;
  if (v.stepMismatch && el instanceof HTMLInputElement) {
    const step = el.step;
    if (step === "1") return "Use a whole number.";
    const decimals = step.includes(".") ? step.split(".")[1].length : 0;
    return decimals ? `Use up to ${decimals} decimal place${decimals === 1 ? "" : "s"}.` : `Use steps of ${step}.`;
  }
  if (v.patternMismatch) return el.dataset.patternMessage || el.title || "Check the format.";
  if (v.customError) return el.validationMessage;
  return el.validationMessage || "Check this value.";
}

/** Label + control + hint/error, wired together with ids for screen readers.
 *
 *  Validation: put the rules on the control itself (`required`, `type="email"`, `min`, `max`, `maxLength`, `pattern`,
 *  `step`). When the form is submitted the browser checks them; instead of its pop-up bubble the field shows the
 *  message under the control, marks it invalid, and the first invalid field in the form takes focus. The message
 *  clears as soon as the value is fixed. A required control gets a `*` beside its label without anything else to set.
 *  An `error` passed in (for example from the server) wins over the browser's own message. */
export function Field({
  label,
  hint,
  error,
  children,
  className,
  hideLabel,
  tip,
}: {
  label: string;
  hint?: React.ReactNode;
  error?: string;
  className?: string;
  /** Keep the label for screen readers but don't show it (a search box with a clear placeholder). */
  hideLabel?: boolean;
  /** A plain-words explanation of a field that is easy to get wrong. Shows an ⓘ beside the label that opens it in place
   *  (works with a tap as well as a mouse). Keep the wording in modules/help/tips.ts. */
  tip?: React.ReactNode;
  children: (props: { id: string; "aria-describedby"?: string; "aria-invalid"?: boolean }) => React.ReactNode;
}) {
  const id = useId();
  const box = useRef<HTMLDivElement>(null);
  const [own, setOwn] = useState<string | undefined>();
  const [required, setRequired] = useState(false);
  const [tipOpen, setTipOpen] = useState(false);
  const tipId = `${id}-tip`;
  const shown = error ?? own;
  const errorId = shown ? `${id}-error` : undefined;
  const hintId = hint && !shown ? `${id}-hint` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  const controlOf = useCallback((): Control | null => {
    const el = box.current?.querySelector<Control>(`[id="${CSS.escape(id)}"]`) ?? box.current?.querySelector<Control>("input,select,textarea");
    return el ?? null;
  }, [id]);

  // A required control earns its marker; checked after every render because `required` can change.
  useLayoutEffect(() => {
    const el = controlOf();
    const r = !!el && el.required && !el.disabled && !("readOnly" in el && el.readOnly);
    if (r !== required) setRequired(r);
  });

  useEffect(() => {
    const root = box.current;
    if (!root) return;
    const onInvalid = (e: Event) => {
      const el = e.target as Control;
      e.preventDefault(); // no browser bubble: the message is shown inline instead
      setOwn(validityMessage(el, label));
      const form = el.form;
      const first = form?.querySelector<Control>("input:invalid,select:invalid,textarea:invalid");
      if (!form || first === el) {
        el.focus({ preventScroll: true });
        el.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    };
    const onChange = (e: Event) => {
      const el = e.target as Control;
      if (!("validity" in el)) return;
      setOwn((cur) => (cur === undefined ? cur : el.validity.valid ? undefined : validityMessage(el, label)));
    };
    root.addEventListener("invalid", onInvalid, true);
    root.addEventListener("input", onChange, true);
    root.addEventListener("change", onChange, true);
    return () => {
      root.removeEventListener("invalid", onInvalid, true);
      root.removeEventListener("input", onChange, true);
      root.removeEventListener("change", onChange, true);
    };
  }, [label]);

  return (
    <div ref={box} className={cn("min-w-0 space-y-1", className)}>
      {tip ? (
        <div className={cn("mb-1 flex items-center gap-1", hideLabel && "sr-only")}>
          <Label htmlFor={id} className="mb-0">
            {label}
            {required && <span aria-hidden="true" className="ml-0.5 text-danger">*</span>}
          </Label>
          <button type="button" onClick={() => setTipOpen((o) => !o)} aria-expanded={tipOpen} aria-controls={tipId}
            className="grid size-5 shrink-0 place-items-center rounded-full text-muted hover:bg-sand hover:text-accent focus-visible:outline-2">
            <Icon name="info" className="size-4" />
            <span className="sr-only">About {label.replace(/\s*\(.*\)\s*$/, "").toLowerCase()}</span>
          </button>
        </div>
      ) : (
        <Label htmlFor={id} className={hideLabel ? "sr-only" : undefined}>
          {label}
          {required && <span aria-hidden="true" className="ml-0.5 text-danger">*</span>}
        </Label>
      )}
      {tip && tipOpen && (
        <div id={tipId} role="note" className="rounded-[var(--radius-control)] bg-canvas px-3 py-2 text-xs leading-relaxed text-ink/85">{tip}</div>
      )}
      {children({ id, "aria-describedby": describedBy, "aria-invalid": shown ? true : undefined })}
      {hint && !shown && (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      )}
      {shown && (
        <p id={errorId} role="alert" className="flex items-start gap-1 text-xs font-medium text-danger">
          <svg aria-hidden="true" viewBox="0 0 16 16" className="mt-px size-3.5 shrink-0" fill="currentColor">
            <path d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Zm-.75 3.25h1.5v4.5h-1.5v-4.5Zm0 5.75h1.5V12h-1.5v-1.5Z" />
          </svg>
          <span>{shown}</span>
        </p>
      )}
    </div>
  );
}

/** The buttons at the end of a row of fields (a filter bar, an inline "add" form). An invisible line the height of a
 *  field label sits above them, so the buttons line up with the inputs even when a field in the row has a hint or an
 *  error under it; the buttons take the controls' height. Use it in a row aligned to the top (`items-start`). */
export function FieldActions({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0 space-y-1", className)}>
      <span aria-hidden="true" className="mb-1 hidden select-none text-sm font-semibold sm:block">&nbsp;</span>
      <div className={cn("flex flex-wrap items-center gap-2 [&>a]:h-9 [&>button]:h-9")}>{children}</div>
    </div>
  );
}
