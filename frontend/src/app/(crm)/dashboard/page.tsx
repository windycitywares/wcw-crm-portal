"use client";

import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import { MyTasksPanel } from "@/modules/tasks/MyTasksPanel";
import { LeadSummaryCard } from "@/modules/leads/LeadSummaryCard";
import { SalesSummaryCard } from "@/modules/sales/SalesSummaryCard";

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
          <PanelHeader title="Quick links" />
          <PanelBody className="space-y-1">
            <Link href="/account" className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-2 py-2 text-sm hover:bg-sand">
              <Icon name="key" className="size-4 text-muted" />
              Your profile and password
            </Link>
            <Link href="/contacts" className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-2 py-2 text-sm hover:bg-sand">
              <Icon name="customers" className="size-4 text-muted" />
              Contacts
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
