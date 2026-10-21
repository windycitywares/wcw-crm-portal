"use client";

import Link from "next/link";
import { NAV } from "@/components/layout/nav";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth";

/** What each settings section is for, in the order the sidebar lists them. */
const ABOUT: Record<string, string> = {
  "/settings/users": "Who can sign in, their role and what they can do.",
  "/settings/types": "The customer types you pick from.",
  "/settings/tags": "Tags for grouping customers and work.",
  "/settings/pipelines": "Sales pipelines and their stages.",
  "/settings/custom-fields": "Extra fields on customers, leads and deals.",
  "/settings/email": "Sending domain and default email settings.",
  "/settings/email-accounts": "The mailboxes the team reads and replies from.",
  "/settings/business-hours": "When the team is available and how holidays count.",
  "/settings/sla-policies": "Response targets for tickets.",
  "/settings/canned-responses": "Saved replies for common questions.",
  "/settings/integrations": "The shop connection and other services.",
  "/settings/deployments": "Deploy history and what is live.",
  "/settings/audit": "Who changed what, newest first.",
};

export default function SettingsHome() {
  const { can } = useAuth();
  const sections = (NAV.find((g) => g.label === "Administration")?.items ?? []).filter(
    (i) => i.hidden && (!i.permission || can(i.permission)),
  );
  return (
    <div>
      <PageHeader
        title="Settings"
        description="Everything the CRM runs on: the team, the lists you pick from, email, hours and integrations. Every change is recorded in the audit log."
      />
      <ul className="grid gap-3 sm:grid-cols-2">
        {sections.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className="flex h-full items-start gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-4 hover:border-ink/30"
            >
              <Icon name={item.icon} className="mt-0.5 size-5 text-muted" />
              <span className="min-w-0">
                <span className="block text-sm font-medium">{item.label}</span>
                <span className="mt-0.5 block text-sm text-muted">{ABOUT[item.href]}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
