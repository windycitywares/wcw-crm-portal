"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { formatDateTime, timeAgo } from "@/lib/utils";
import { recordsApi, type Activity, type RecordRef } from "./api";
import { useDirectory } from "./useDirectory";

/** Icons by the first part of the activity kind ("note.added" → note). Modules add theirs here. */
const ICONS: Record<string, IconName> = {
  note: "edit",
  tags: "tag",
  order: "cart",
  email: "mail",
  ticket: "ticket",
  task: "tasks",
  deal: "briefcase",
  campaign: "mail",
};

/** A record's history, newest first. Pass a changing `refreshKey` to reload after edits. */
export function Timeline({ record, refreshKey }: { record: RecordRef; refreshKey?: unknown }) {
  const { name } = useDirectory();
  const [items, setItems] = useState<Activity[] | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const load = useCallback(
    async (p: number) => {
      setLoading(true);
      try {
        const res = await recordsApi.timeline(record, p);
        setItems((prev) => (p === 1 ? res.items : [...(prev ?? []), ...res.items]));
        setTotal(res.total);
        setPage(p);
      } catch {
        setItems((prev) => prev ?? []);
      } finally {
        setLoading(false);
      }
    },
    [record.type, record.id], // eslint-disable-line react-hooks/exhaustive-deps
  );

  useEffect(() => {
    void load(1);
  }, [load, refreshKey]);

  return (
    <Panel>
      <PanelHeader title="Activity" />
      <ol className="px-5 py-3">
        {items === null && <li className="skeleton my-2 h-4 w-1/2" aria-hidden="true" />}
        {items?.length === 0 && <li className="py-4 text-center text-sm text-muted">Nothing has happened here yet.</li>}
        {items?.map((a) => {
          const preview = typeof a.data?.preview === "string" ? a.data.preview : null;
          return (
            <li key={a.id} className="relative flex gap-3 pb-4 last:pb-0">
              <span aria-hidden="true" className="relative z-10 mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-sand text-muted">
                <Icon name={ICONS[a.kind.split(".")[0]] ?? "clock"} className="size-3.5" />
              </span>
              <div className="min-w-0 text-sm">
                <p>
                  <span className="font-medium">{a.title}</span> <span className="text-muted">· {name(a.actor_id)}</span>
                </p>
                {preview && <p className="truncate text-muted">{preview}</p>}
                <time dateTime={a.at} title={formatDateTime(a.at)} className="text-xs text-muted">
                  {timeAgo(a.at)}
                </time>
              </div>
            </li>
          );
        })}
      </ol>
      {items && items.length < total && (
        <div className="border-t border-line px-5 py-3">
          <Button size="sm" variant="ghost" disabled={loading} onClick={() => void load(page + 1)}>
            {loading ? "Loading…" : "Show older"}
          </Button>
        </div>
      )}
    </Panel>
  );
}
