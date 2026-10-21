"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { TrendSparkline } from "@/components/ui/TrendSparkline";
import { useAuth } from "@/lib/auth";
import { MyTasksPanel } from "@/modules/tasks/MyTasksPanel";
import { LeadSummaryCard } from "@/modules/leads/LeadSummaryCard";
import { SalesSummaryCard } from "@/modules/sales/SalesSummaryCard";

const statCards = [
  {
    title: "Total customers",
    value: "1,234",
    subtitle: "32 new this week",
    icon: "customers",
    trend: { label: "+2.1% vs last week", delta: 2.1, up: true },
  },
  {
    title: "Open tickets",
    value: "42",
    subtitle: "5 overdue",
    icon: "ticket",
    trend: { label: "-8 vs yesterday", delta: 8, up: false },
  },
  {
    title: "Active campaigns",
    value: "6",
    subtitle: "24,500 recipients",
    icon: "mail",
    trend: { label: "+12% open rate", delta: 12, up: true },
  },
  {
    title: "Open pipeline",
    value: "$84,200",
    subtitle: "18 deals",
    icon: "briefcase",
    trend: { label: "+5.4% this month", delta: 5.4, up: true },
  },
] as const;

const quickActions = [
  { label: "New customer", href: "/customers/new", icon: "users" },
  { label: "New contact", href: "/contacts", icon: "customers" },
  { label: "New ticket", href: "/tickets", icon: "ticket" },
  { label: "New task", href: "/tasks", icon: "tasks" },
  { label: "New campaign", href: "/campaigns/new", icon: "mail" },
  { label: "New deal", href: "/sales", icon: "briefcase" },
] as const;

const recentActivity = [
  { time: "2h ago", actor: "Maria Chen", action: "updated order #1042", target: "to delivered" },
  { time: "5h ago", actor: "David Park", action: "created contact", target: "Acme Corp" },
  { time: "1d ago", actor: "Sam Rivera", action: "closed ticket", target: "return request" },
  { time: "2d ago", actor: "Maria Chen", action: "sent campaign", target: "Summer sale" },
] as const;

export default function DashboardPage() {
  const { user, can } = useAuth();
  const first = user?.full_name.split(" ")[0] ?? "there";
  const [stats, setStats] = useState<{ customers: number; tickets: number; campaigns: number; pipeline: number } | null>(null);

  useEffect(() => {
    // Placeholder: wire to real APIs as they become available
    setStats({ customers: 1234, tickets: 42, campaigns: 6, pipeline: 84200 });
  }, []);

  return (
    <>
      <PageHeader
        title={`Welcome, ${first}`}
        description="Your CRM workspace. At a glance: customers, tickets, campaigns and pipeline."
        actions={
          <div className="flex items-center gap-2">
            <Link
              href="/reports"
              className="flex items-center gap-2 rounded-[var(--radius-control)] border border-line bg-surface px-3 py-2 text-sm font-medium text-ink hover:border-accent hover:bg-accent/10">
              <Icon name="chart" className="size-4 text-muted" />
              Full reports
            </Link>
          </div>
        }
      />

      {/* Stat cards */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => (
          <StatCard key={card.title} {...card} />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        {/* Left column: tasks, leads, sales */}
        <div className="flex flex-col gap-6">
          {can("tasks:view") && <MyTasksPanel />}
          {can("sales:view") && <LeadSummaryCard />}
          {can("sales:view") && <SalesSummaryCard />}
        </div>

        {/* Right column: quick actions + recent activity */}
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader title="Quick actions" description="Common tasks to get started." />
            <CardBody className="p-4">
              <div className="grid gap-2 sm:grid-cols-2">
                {quickActions.map((action) => (
                  <Link
                    key={action.label}
                    href={action.href}
                    className="flex items-center gap-2.5 rounded-[var(--radius-control)] border border-line bg-surface px-3 py-2.5 text-sm font-medium text-ink hover:border-accent hover:bg-accent/5 transition-colors">
                    <Icon name={action.icon} className="size-4 text-muted" />
                    {action.label}
                  </Link>
                ))}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Recent activity" description="Latest updates across customers, tickets and orders." />
            <CardBody className="p-4">
              <div className="space-y-3">
                {recentActivity.map((item, i) => (
                  <div key={i} className="flex gap-3">
                    <div className="mt-1.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-night/10 text-night">
                      <Icon name="clock" className="size-3" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ink leading-none">{item.actor}</p>
                      <p className="text-xs text-muted leading-none">{item.action} {item.target}</p>
                      <p className="text-xs text-muted">{item.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}
