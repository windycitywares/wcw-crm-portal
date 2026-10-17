"use client";

import Link from "next/link";
import { Icon, type IconName } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useAuth } from "@/lib/auth";
import { MyTasksPanel } from "@/modules/tasks/MyTasksPanel";
import { LeadSummaryCard } from "@/modules/leads/LeadSummaryCard";
import { SalesSummaryCard } from "@/modules/sales/SalesSummaryCard";

const ROADMAP: { icon: IconName; title: string; text: string; milestone: string }[] = [
  { icon: "customers", title: "Customers", text: "Every buyer in one place, with types, tags and their shop orders.", milestone: "Live" },
  { icon: "tasks", title: "Tasks", text: "Calls, follow-ups and to-dos with due dates and reminders.", milestone: "Live" },
  { icon: "ticket", title: "Support tickets", text: "Returns, damages and questions with response-time targets.", milestone: "M3" },
  { icon: "briefcase", title: "Sales", text: "Deals on a pipeline board, with a weighted forecast.", milestone: "Live" },
  { icon: "mail", title: "Campaigns", text: "Email templates, target lists and sending.", milestone: "M5" },
  { icon: "truck", title: "Suppliers", text: "Suppliers, their types and what they supply.", milestone: "M6" },
];

export default function DashboardPage() {
  const { user, can } = useAuth();
  const first = user?.full_name.split(" ")[0] ?? "there";
  return (
    <>
      <PageHeader title={`Welcome, ${first}`} description="Your CRM workspace. Modules appear in the sidebar as they're released." />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        {can("tasks:view") && <MyTasksPanel />}
        {can("sales:view") && <LeadSummaryCard />}
        {can("sales:view") && <SalesSummaryCard />}
        <Panel>
          <PanelHeader title="Coming next" description="The build order agreed in the CRM spec." />
          <ul className="grid gap-px bg-line sm:grid-cols-2">
            {ROADMAP.map((m) => (
              <li key={m.title} className="flex gap-3 bg-surface p-5">
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-accent-soft text-accent-strong">
                  <Icon name={m.icon} className="size-[1.1rem]" />
                </span>
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-medium">
                    {m.title}
                    <Pill dot={false}>{m.milestone}</Pill>
                  </p>
                  <p className="mt-0.5 text-sm text-muted">{m.text}</p>
                </div>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <PanelHeader title="Quick links" />
          <PanelBody className="space-y-1">
            <Link href="/account" className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-2 py-2 text-sm hover:bg-sand">
              <Icon name="key" className="size-4 text-muted" />
              Your profile and password
            </Link>
            {can("users:manage") && (
              <Link href="/settings/users" className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-2 py-2 text-sm hover:bg-sand">
                <Icon name="users" className="size-4 text-muted" />
                Invite your team
              </Link>
            )}
            {can("audit:view") && (
              <Link href="/settings/audit" className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-2 py-2 text-sm hover:bg-sand">
                <Icon name="shield" className="size-4 text-muted" />
                Audit log
              </Link>
            )}
          </PanelBody>
        </Panel>
      </div>
    </>
  );
}
