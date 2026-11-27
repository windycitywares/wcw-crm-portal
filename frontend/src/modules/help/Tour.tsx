"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { TOURS } from "./content/tours";
import { topicFor } from "./content";
import type { TourStep } from "./types";

const SEEN = "wcw-tour-seen:";
const seen = (id: string) => { try { return localStorage.getItem(SEEN + id) === "1"; } catch { return true; } };
const markSeen = (id: string) => { try { localStorage.setItem(SEEN + id, "1"); } catch { /* private mode: it will be offered again, which is harmless */ } };

/** Finds what a step points at: a CSS selector, or the first button, link, heading or label whose text contains `text`. */
function locate(step: TourStep): HTMLElement | null {
  const visible = (el: Element | null): HTMLElement | null => {
    const h = el as HTMLElement | null;
    return h && h.offsetParent !== null ? h : null;
  };
  if (step.selector) {
    for (const el of Array.from(document.querySelectorAll(step.selector))) {
      if (visible(el)) return el as HTMLElement;
    }
  }
  if (step.text) {
    const t = step.text.toLowerCase();
    const found = Array.from(document.querySelectorAll("main button, main a, main h2, main h3, main label, main [role=tab]")).find(
      (el) => (el.textContent ?? "").toLowerCase().includes(t) && visible(el),
    );
    if (found) return found as HTMLElement;
  }
  return null;
}

/** Offers a short tour the first time a page with one is opened, and runs a tour when asked. */
export function TourHost({ running, onStop, onStart, panelOpen }: {
  running: string | null;
  onStop: () => void;
  onStart: (topicId: string) => void;
  panelOpen: boolean;
}) {
  const pathname = usePathname();
  const [offer, setOffer] = useState<string | null>(null);

  // A page with a tour that has not been offered here yet: ask, a moment after it has loaded.
  useEffect(() => {
    setOffer(null);
    const topic = topicFor(pathname);
    if (!topic || !TOURS[topic.id] || seen(topic.id)) return;
    const timer = window.setTimeout(() => setOffer(topic.id), 1500);
    return () => window.clearTimeout(timer);
  }, [pathname]);

  // The tour ends if you leave the page it is about.
  useEffect(() => { if (running) onStop(); }, [pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  if (running) return <TourCard id={running} onClose={() => { markSeen(running); onStop(); }} />;
  if (offer && !panelOpen) {
    const dismiss = () => { markSeen(offer); setOffer(null); };
    return (
      <div role="region" aria-label="Page tour" className="fixed inset-x-3 bottom-3 z-[55] rounded-[var(--radius-card)] bg-surface p-4 shadow-[var(--shadow-raised)] ring-1 ring-line sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-80">
        <p className="text-sm font-semibold text-ink">New to this page?</p>
        <p className="mt-1 text-sm text-muted">Take a one-minute tour of what is where.</p>
        <div className="mt-3 flex gap-2">
          <Button size="sm" onClick={() => { setOffer(null); onStart(offer); }}>Show me around</Button>
          <Button size="sm" variant="ghost" onClick={dismiss}>No thanks</Button>
        </div>
      </div>
    );
  }
  return null;
}

function TourCard({ id, onClose }: { id: string; onClose: () => void }) {
  const steps = TOURS[id] ?? [];
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const next = useRef<HTMLButtonElement>(null);
  const step = steps[i];

  const place = useCallback(() => {
    const el = step ? locate(step) : null;
    setRect(el ? el.getBoundingClientRect() : null);
  }, [step]);

  useLayoutEffect(() => {
    const el = step ? locate(step) : null;
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
    place();
    // Smooth scrolling moves the target after this runs, so measure again once it settles.
    const t = window.setTimeout(place, 400);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => { window.clearTimeout(t); window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true); };
  }, [step, place]);

  useEffect(() => { next.current?.focus(); }, [i]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight") setI((n) => Math.min(n + 1, steps.length - 1));
      else if (e.key === "ArrowLeft") setI((n) => Math.max(n - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, steps.length]);

  if (!step) return null;
  const last = i === steps.length - 1;
  return (
    <>
      {rect && (
        <div aria-hidden="true" className="pointer-events-none fixed z-[65] rounded-[var(--radius-control)] ring-2 ring-accent transition-all duration-200"
          style={{ top: rect.top - 6, left: rect.left - 6, width: rect.width + 12, height: rect.height + 12, boxShadow: "0 0 0 9999px rgb(0 0 0 / 0.35)" }} />
      )}
      <div role="dialog" aria-label="Page tour" className="fixed inset-x-3 bottom-3 z-[70] rounded-[var(--radius-card)] bg-surface p-4 shadow-[var(--shadow-raised)] ring-1 ring-line sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-96">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Step {i + 1} of {steps.length}</p>
        <h2 className="mt-1 text-base font-semibold text-ink">{step.title}</h2>
        <p className="mt-1 text-sm leading-relaxed text-ink/85">{step.body}</p>
        <div className="mt-4 flex items-center justify-between gap-2">
          <Button size="sm" variant="ghost" onClick={onClose}>{last ? "Close" : "Skip tour"}</Button>
          <div className="flex gap-2">
            {i > 0 && <Button size="sm" variant="secondary" onClick={() => setI(i - 1)}>Back</Button>}
            <button ref={next} type="button" onClick={() => (last ? onClose() : setI(i + 1))}
              className="inline-flex h-9 items-center rounded-[var(--radius-control)] bg-accent px-3 text-sm font-medium text-white hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2">
              {last ? "Done" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
