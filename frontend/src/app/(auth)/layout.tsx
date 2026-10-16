import { Logo } from "@/components/ui/Logo";

/** Signed-out frame: a single centred card. */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="grid min-h-dvh place-items-center bg-night px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <Logo tone="reverse" className="h-9 w-auto" />
          <span className="rounded-full border border-white/20 px-2 py-0.5 text-xs font-semibold tracking-wide text-night-muted">CRM</span>
        </div>
        <div className="rounded-[var(--radius-card)] border border-line bg-surface p-6 shadow-[0_24px_60px_-24px_rgb(0_0_0/0.6)] sm:p-7">{children}</div>
        <p className="mt-6 text-center text-xs text-night-muted">Windy City Wares · staff only</p>
      </div>
    </main>
  );
}
