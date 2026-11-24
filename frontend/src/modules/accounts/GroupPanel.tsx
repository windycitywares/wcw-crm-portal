"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { money } from "@/components/charts/format";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { cn } from "@/lib/utils";
import { accountsApi, type Account, type AccountGroup } from "./api";

/** Where the account sits in its group: the organisations above it, every sub-account under it, and the
 *  totals of the whole branch (people counted once even when they are at two companies in it). */
export function GroupPanel({ account }: { account: Account }) {
  const [group, setGroup] = useState<AccountGroup | null>(null);
  const inGroup = account.parent_id !== null || account.children_count > 0;

  useEffect(() => {
    if (!inGroup) return;
    let alive = true;
    accountsApi.group(account.id).then((g) => alive && setGroup(g)).catch(() => alive && setGroup(null));
    return () => { alive = false; };
  }, [account.id, account.updated_at, inGroup]);

  if (!inGroup || !group) return null;
  const subs = group.tree.length - 1;

  return (
    <Panel>
      <PanelHeader title="Group"
        description={subs ? `${subs} sub-account${subs === 1 ? "" : "s"} under ${account.name}.` : "This account is part of a group."} />
      <PanelBody className="space-y-4">
        {group.ancestors.length > 0 && (
          <nav aria-label="Parent accounts" className="text-sm">
            <ol className="flex flex-wrap items-center gap-1 text-muted">
              {group.ancestors.map((a) => (
                <li key={a.id} className="flex items-center gap-1">
                  <Link href={`/accounts/${a.id}`} className="text-accent-strong hover:underline">{a.name}</Link>
                  <span aria-hidden="true">›</span>
                </li>
              ))}
              <li aria-current="page" className="font-medium text-ink">{account.name}</li>
            </ol>
          </nav>
        )}
        {subs > 0 && (
          <>
            <dl className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-3 text-center">
              <Stat label="People in this branch" value={String(group.people)} />
              <Stat label="Open deals" value={String(group.open_deals)} />
              <Stat label="Open value" value={money(group.open_value)} />
            </dl>
            <ul className="divide-y divide-line text-sm">
              {group.tree.map((n) => (
                <li key={n.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="flex min-w-0 items-center" style={{ paddingLeft: `${n.depth * 1}rem` }}>
                    {n.depth > 0 && <span aria-hidden="true" className="mr-2 text-muted">└</span>}
                    {n.id === account.id
                      ? <span className="truncate font-medium">{n.name}</span>
                      : <Link href={`/accounts/${n.id}`} className={cn("truncate hover:text-accent-strong hover:underline", n.status !== "active" && "text-muted")}>{n.name}</Link>}
                  </span>
                  <span className="shrink-0 text-xs text-muted">
                    {n.contacts_count} {n.contacts_count === 1 ? "person" : "people"} · {n.open_deals} open {n.open_deals === 1 ? "deal" : "deals"}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </PanelBody>
    </Panel>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-control)] bg-sand/50 px-2 py-3">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}
