import { Logo } from "@/components/ui/Logo";

/** Signed-out frame: a single centred white card on the admin's soft grey-blue ground (as in the shop admin). */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="grid min-h-dvh place-items-center bg-canvas px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <Logo title="WindyCityWares" className="h-8 w-auto" />
          <span className="font-admin rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-bold tracking-wide text-accent">CRM</span>
        </div>
        <div className="rounded-[var(--radius-card)] bg-surface p-6 shadow-[var(--shadow-raised)] sm:p-7">{children}</div>
        <p className="mt-6 text-center text-xs text-muted">Windy City Wares · staff only</p>
      </div>
    </main>
  );
}
