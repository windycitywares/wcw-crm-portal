"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { useLive, type LiveEvent } from "@/lib/live";

/**
 * "3 new updates · Refresh" above a list when something it shows changed elsewhere (as in the shop admin).
 * It never reloads by itself, so nobody loses their place, their filters or a half-typed edit.
 */
export function LiveUpdatesBar({
  types,
  noun,
  onRefresh,
}: {
  /** Record types the list shows, e.g. ["ticket"]. */
  types: string[];
  /** What the list holds, for the message: "contact" → "2 contacts added or changed". */
  noun: string;
  onRefresh: () => void;
}) {
  const [pending, setPending] = useState<LiveEvent[]>([]);
  useLive(types, (events) => setPending((p) => [...p, ...events]));
  if (!pending.length) return null;
  const records = new Set(pending.map((e) => `${e.entity_type}:${e.ref_id}`)).size;
  const added = pending.some((e) => e.kind.endsWith(".create") || e.kind.endsWith(".inbound"));
  const who = pending[pending.length - 1]?.actor_name;
  const text = `${records} ${noun}${records === 1 ? "" : "s"} ${added ? "added or changed" : "changed"}${who ? ` (latest by ${who})` : ""}`;
  return (
    <div role="status" className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-card)] border border-accent/30 bg-accent/10 px-4 py-2.5 text-sm">
      <span className="flex items-center gap-2 font-medium">
        <Icon name="bell" className="size-4 text-accent" />
        {text}
      </span>
      <Button
        size="sm"
        variant="secondary"
        onClick={() => {
          setPending([]);
          onRefresh();
        }}
      >
        Refresh
      </Button>
    </div>
  );
}
