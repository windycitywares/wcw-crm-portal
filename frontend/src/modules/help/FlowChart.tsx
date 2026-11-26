import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { cn } from "@/lib/utils";
import { FLOWS } from "./flows";
import type { FlowId } from "./types";

/** The order things are done in, one box per page. The box for the page you are on is highlighted; every box opens its page. */
export function FlowChart({ id, step, onNavigate }: { id: FlowId; step?: string; onNavigate?: () => void }) {
  const flow = FLOWS[id];
  return (
    <div>
      <p className="mb-3 text-sm text-muted">{flow.intro}</p>
      <ol aria-label={flow.title} className="m-0 list-none p-0">
        {flow.nodes.map((n, i) => {
          const here = n.id === step;
          return (
            <li key={n.id} className="relative pl-9">
              {i < flow.nodes.length - 1 && <span aria-hidden="true" className="absolute left-[0.8125rem] top-8 h-[calc(100%-1rem)] w-px bg-line" />}
              <span aria-hidden="true" className={cn("absolute left-0 top-1.5 grid size-7 place-items-center rounded-full text-xs font-semibold", here ? "bg-accent text-white" : "bg-sand text-muted")}>{i + 1}</span>
              <Link href={n.href} onClick={onNavigate} aria-current={here ? "step" : undefined}
                className={cn("mb-2 block rounded-[var(--radius-control)] border px-3 py-2 text-sm hover:border-accent focus-visible:outline-2",
                  here ? "border-accent bg-accent/5" : "border-line bg-surface")}>
                <span className="flex items-center justify-between gap-2 font-medium text-ink">
                  {n.label}
                  {here ? <span className="rounded-full bg-accent px-2 py-0.5 text-[0.6875rem] font-semibold text-white">You are here</span> : <Icon name="chevronRight" className="size-4 text-muted" />}
                </span>
                <span className="mt-0.5 block text-xs text-muted">{n.note}</span>
              </Link>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
