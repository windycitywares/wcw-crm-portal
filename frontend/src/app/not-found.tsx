import type { Metadata } from "next";
import { NotFoundMessage } from "@/components/layout/NotFoundMessage";
import { Logo } from "@/components/ui/Logo";

export const metadata: Metadata = { title: "Page not found" };

/** Fallback 404 outside the CRM frame (the CRM frame's own is `(crm)/not-found.tsx`). */
export default function NotFound() {
  return (
    <main className="min-h-dvh bg-canvas">
      <div className="flex items-center justify-center gap-2.5 pt-10">
        <Logo title="WindyCityWares" className="h-8 w-auto" />
        <span className="font-admin rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-bold tracking-wide text-accent">CRM</span>
      </div>
      <NotFoundMessage />
    </main>
  );
}
