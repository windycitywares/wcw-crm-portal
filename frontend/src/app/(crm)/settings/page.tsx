"use client";

import Link from "next/link";
import { SETTINGS_NAV } from "@/components/layout/nav";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth";

const ABOUT: Record<string, string> = {
  "/settings/users": "Who can sign in, and their role.",
  "/settings/audit": "Every change, who made it and when.",
  "/settings/types": "Customer, ticket, task and supplier types, sources and more.",
  "/settings/tags": "The labels you put on customers and other records.",
  "/settings/custom-fields": "Extra fields your team fills in on records.",
  "/settings/pipelines": "The stages deals move through.",
  "/settings/sla-policies": "Response and resolution targets for tickets.",
  "/settings/canned-responses": "Saved replies for tickets and the inbox.",
  "/settings/business-hours": "Opening hours and holidays the SLA clock follows.",
  "/settings/email": "The mailbox the CRM sends from, and its limits.",
  "/settings/email-accounts": "Mailboxes the inbox reads customer email from.",
  "/settings/integrations": "The connection to the shop and other channels.",
  "/settings/deployments": "When merged changes go live, and the deploy log.",
  "/settings/environment": "Work on a copy of the data without touching the real one.",
};

/** All settings at a glance (as the shop admin's "All settings"); the sidebar lists the same sections. */
export default function SettingsHome() {
  const { can } = useAuth();
  const groups = SETTINGS_NAV.map((g) => ({ ...g, items: g.items.filter((i) => !i.permission || can(i.permission)) })).filter(
    (g) => g.items.length > 0,
  );
  return (
    <>
      <PageHeader title="Settings" description="Everything the CRM runs on. Every change is recorded in the audit log." />
      {groups.length === 0 ? (
        <p className="text-sm text-muted">Your role has no settings to change.</p>
      ) : (
        <div className="space-y-8">
          {groups.map((g) => (
            <section key={g.label} aria-labelledby={`settings-${g.label}`}>
              <h2 id={`settings-${g.label}`} className="font-admin mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
                {g.label}
              </h2>
              <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {g.items.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="group flex h-full items-start gap-4 rounded-[var(--radius-card)] bg-surface p-5 shadow-[var(--shadow-card)] transition-shadow hover:shadow-[var(--shadow-raised)]"
                    >
                      <span aria-hidden="true" className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
                        <Icon name={item.icon} className="size-5" />
                      </span>
                      <span className="min-w-0">
                        <span className="font-admin block font-semibold text-ink group-hover:text-accent">{item.label}</span>
                        {ABOUT[item.href] && <span className="mt-0.5 block text-sm text-muted">{ABOUT[item.href]}</span>}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
