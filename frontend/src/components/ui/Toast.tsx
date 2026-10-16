"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Icon } from "./Icon";

interface ToastInput {
  tone?: "success" | "danger" | "info";
  title: string;
  description?: string;
}
interface ToastItem extends ToastInput {
  id: number;
}

const Ctx = createContext<{ push: (t: ToastInput) => void } | null>(null);

/** Confirmations and errors that don't need a whole page. Same verb as the button ("Saved", "Published"). */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const dismiss = useCallback((id: number) => setItems((l) => l.filter((t) => t.id !== id)), []);
  const push = useCallback(
    (t: ToastInput) => {
      const id = nextId.current++;
      setItems((l) => [...l.slice(-3), { ...t, id }]);
      window.setTimeout(() => dismiss(id), t.tone === "danger" ? 9000 : 4500);
    },
    [dismiss],
  );
  const value = useMemo(() => ({ push }), [push]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-4 bottom-4 z-[60] flex flex-col items-end gap-2 sm:left-auto sm:right-6">
        {items.map((t) => (
          <div
            key={t.id}
            role={t.tone === "danger" ? "alert" : "status"}
            className={cn(
              "toast-in pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-[var(--radius-card)] border bg-surface px-4 py-3 text-sm shadow-[0_12px_32px_-12px_rgb(0_0_0/0.4)]",
              t.tone === "danger" ? "border-danger/40" : t.tone === "info" ? "border-line" : "border-success/40",
            )}
          >
            <Icon name={t.tone === "danger" ? "alert" : "check"} className={cn("mt-0.5 size-4", t.tone === "danger" ? "text-danger" : t.tone === "info" ? "text-muted" : "text-success")} strokeWidth={2} />
            <div className="min-w-0 flex-1">
              <p className="font-medium">{t.title}</p>
              {t.description && <p className="mt-0.5 text-muted">{t.description}</p>}
            </div>
            <button type="button" onClick={() => dismiss(t.id)} className="-mr-1 grid size-6 place-items-center rounded-full text-muted hover:bg-sand hover:text-ink">
              <Icon name="close" className="size-3.5" />
              <span className="sr-only">Dismiss</span>
            </button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}
