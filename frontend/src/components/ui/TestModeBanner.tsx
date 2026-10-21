"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/client-api";

/**
 * A bar across the top of every page while the CRM runs on the test copy of its data.
 * Checked in the browser, so it appears and disappears without rebuilding or re-caching any page.
 */
export function TestModeBanner({ label, text, children }: { label: string; text: string; children?: React.ReactNode }) {
  const [test, setTest] = useState(false);
  useEffect(() => {
    let live = true;
    const check = () =>
      fetch(`${API_URL}/environment`, { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : { test: false }))
        .then((d: { test?: boolean }) => live && setTest(Boolean(d.test)))
        .catch(() => undefined);
    check();
    const timer = window.setInterval(check, 60_000);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, []);
  if (!test) return null;
  return (
    <aside aria-label={label} className="relative z-40 bg-warning px-4 py-2 text-center text-sm font-medium text-canvas">
      {text}
      {children}
    </aside>
  );
}
