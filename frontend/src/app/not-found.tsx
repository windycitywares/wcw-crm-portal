import type { Metadata } from "next";
import { ButtonLink } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";

export const metadata: Metadata = { title: "Page not found" };

/** The CRM's 404, laid out like the shop's: a quiet eyebrow, one large line, a short reason and the way back. */
export default function NotFound() {
  return (
    <main className="grid min-h-dvh place-items-center bg-canvas px-4 py-16">
      <div className="w-full max-w-xl text-center">
        <div className="mb-10 flex items-center justify-center gap-2.5">
          <Logo title="WindyCityWares" className="h-8 w-auto" />
          <span className="font-admin rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-bold tracking-wide text-accent">CRM</span>
        </div>
        <p className="text-sm text-muted">Page not found</p>
        <h1 className="mx-auto mt-3 max-w-xl text-4xl sm:text-5xl">We couldn’t find that page</h1>
        <p className="mt-4 text-muted">It may have moved, or the record was removed. Check the address, or start again from the dashboard.</p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <ButtonLink href="/dashboard">Go to the dashboard</ButtonLink>
          <ButtonLink href="/customers" variant="secondary">
            Find a customer
          </ButtonLink>
        </div>
        <p className="mt-12 text-xs text-muted">Windy City Wares · staff only</p>
      </div>
    </main>
  );
}
