"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Icon, type IconName } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/utils";
import { formatMoney } from "@/modules/customers/api";
import { LeadSummaryCard } from "@/modules/leads/LeadSummaryCard";
import { reportsApi, type ReportsOverview } from "@/modules/reports/api";
import { SalesSummaryCard } from "@/modules/sales/SalesSummaryCard";
import { MyTasksPanel } from "@/modules/tasks/MyTasksPanel";
import { usersApi, type AuditEntry } from "@/modules/users/api";

const QUICK_ACTIONS: { label: string; href: string; icon: IconName; permission: string }[] = [
  { label: "New customer", href: "/customers/new", icon: "users", permission: "customers:edit_own" },
  { label: "New ticket", href: "/tickets", icon: "ticket", permission: "tickets:edit" },
  { label: "New task", href: "/tasks", icon: "tasks", permission: "tasks:edit_own" },
  { label: "New deal", href: "/sales", icon: "briefcase", permission: "sales:edit_own" },
  { label: "New campaign", href: "/campaigns/new", icon: "mail", permission: "campaigns:edit" },
  { label: "Contacts", href: "/contacts", icon: "customers", permission: "customers:view" },
];

/** "customer.update" → "updated a customer". Unknown actions fall back to the raw words. */
function describe(e: AuditEntry) {
  const [thing, verb] = e.action.split(".");
  const verbs: Record<string, string> = {
    create: "added", update: "updated", delete: "deleted", restore: "restored", merge: "merged", import: "imported",
    export: "exported", login: "signed in", logout: "signed out",
  };
  const noun = (thing ?? "").replace(/_/g, " ");
  if (verb && verbs[verb]) return `${verbs[verb]} ${["login", "logout"].includes(verb) ? "" : `a ${noun}`}`.trim();
  return e.action.replace(/[._]/g, " ");
}

function greeting(now = new Date()) {
  const h = now.getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function DashboardPage() {
  const { user, can } = useAuth();
  const first = user?.full_name.split(" ")[0] ?? "there";
  const [overview, setOverview] = useState<ReportsOverview | null>(null);
  const [overviewFailed, setOverviewFailed] = useState(false);
  const [activity, setActivity] = useState<AuditEntry[] | null>(null);
  const showStats = can("reports:view");
  const showActivity = can("audit:view");

  useEffect(() => {
    if (showStats) reportsApi.overview(30).then(setOverview).catch(() => setOverviewFailed(true));
    if (showActivity) usersApi.audit({ page_size: 6 }).then((p) => setActivity(p.items)).catch(() => setActivity([]));
  }, [showStats, showActivity]);

  const loading = overview === null && !overviewFailed;
  const o = overview;
  const actions = QUICK_ACTIONS.filter((a) => can(a.permission));

  return (
    <>
      <PageHeader
        title={`${greeting()}, ${first}`}
        description="Your CRM at a glance: customers, support, campaigns and the pipeline."
        actions={
          can("reports:view") ? (
            <Link
              href="/reports"
              className="flex items-center gap-2 rounded-[var(--radius-control)] bg-accent px-4 py-2 text-sm font-medium text-on-accent hover:bg-accent-strong"
            >
              <Icon name="chart" className="size-4" />
              Full reports
            </Link>
          ) : undefined
        }
      />

      {showStats && !overviewFailed && (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard title="Active customers" icon="customers" href="/customers" loading={loading} value={o?.active_customers.toLocaleString() ?? "—"} />
          <StatCard
            title="Open tickets"
            icon="ticket"
            href="/tickets"
            loading={loading}
            value={o?.tickets.open.toLocaleString() ?? "—"}
            subtitle={o ? (o.tickets.overdue ? `${o.tickets.overdue} overdue` : `${o.tickets.unassigned} unassigned`) : undefined}
            tone={o && o.tickets.overdue > 0 ? "danger" : "neutral"}
          />
          <StatCard
            title="Campaign emails (30 days)"
            icon="mail"
            href="/campaigns"
            loading={loading}
            value={o?.campaigns.sent.toLocaleString() ?? "—"}
            subtitle={o ? (o.campaigns.open_rate != null ? `${Math.round(o.campaigns.open_rate * 100)}% opened` : "Nothing sent yet") : undefined}
          />
          <StatCard
            title="Open pipeline"
            icon="briefcase"
            href="/sales"
            loading={loading}
            value={o ? formatMoney(o.sales.open_value) : "—"}
            subtitle={o ? `${o.sales.open_count} open ${o.sales.open_count === 1 ? "deal" : "deals"}` : undefined}
          />
        </div>
      )}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          {can("tasks:view") && <MyTasksPanel />}
          {can("sales:view") && <LeadSummaryCard />}
          {can("sales:view") && <SalesSummaryCard />}
        </div>

        <div className="flex flex-col gap-6">
          {actions.length > 0 && (
            <Card>
              <CardHeader title="Quick actions" />
              <CardBody className="p-4">
                <div className="grid gap-2 sm:grid-cols-2">
                  {actions.map((a) => (
                    <Link
                      key={a.label}
                      href={a.href}
                      className="font-admin flex items-center gap-2.5 rounded-[var(--radius-control)] bg-canvas px-3 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-accent-soft hover:text-accent"
                    >
                      <Icon name={a.icon} className="size-4 text-accent" />
                      {a.label}
                    </Link>
                  ))}
                </div>
              </CardBody>
            </Card>
          )}

          {showActivity && (
            <Card>
              <CardHeader
                title="Recent activity"
                actions={
                  <Link href="/settings/audit" className="text-sm text-accent hover:underline">
                    Audit log
                  </Link>
                }
              />
              <CardBody className="p-4">
                {activity === null ? (
                  <div className="space-y-3" aria-hidden="true">
                    {[0, 1, 2].map((i) => (
                      <div key={i} className="skeleton h-9" />
                    ))}
                  </div>
                ) : activity.length === 0 ? (
                  <p className="text-sm text-muted">Nothing has happened yet.</p>
                ) : (
                  <ul className="space-y-3">
                    {activity.map((e) => (
                      <li key={e.id} className="flex gap-3">
                        <span aria-hidden="true" className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
                          <Icon name="clock" className="size-3.5" />
                        </span>
                        <div className="min-w-0">
                          <p className="truncate text-sm text-ink">
                            <span className="font-medium">{e.actor_email ?? "System"}</span> {describe(e)}
                            {e.entity_id ? <span className="text-muted"> #{e.entity_id}</span> : null}
                          </p>
                          <p className="text-xs text-muted">{timeAgo(e.at)}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
