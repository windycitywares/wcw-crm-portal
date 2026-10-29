import type { IconName } from "@/components/ui/Icon";

export interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  /** Hidden unless the user has this permission (the API enforces it again). */
  permission?: string;
  /** Kept out of the sidebar (reachable from elsewhere). */
  hidden?: boolean;
  /** Shown indented under the item above it. */
  child?: boolean;
}
export interface NavGroup {
  label?: string;
  items: NavItem[];
}

/**
 * The sidebar. Each module adds its entries here when its pages ship (customers in M2, tasks and
 * tickets in M3, sales in M4, campaigns in M5, suppliers in M6, reports in M7).
 */
export const NAV: NavGroup[] = [
  { items: [{ href: "/dashboard", label: "Dashboard", icon: "dashboard" }] },
  {
    label: "Support",
    items: [
      { href: "/inbox", label: "Inbox", icon: "inbox", permission: "tickets:view" },
      { href: "/tickets", label: "Tickets", icon: "ticket", permission: "tickets:view" },
      { href: "/tasks", label: "Tasks", icon: "tasks", permission: "tasks:view" },
    ],
  },
  {
    label: "Customers",
    items: [
      { href: "/customers", label: "Customers", icon: "customers", permission: "customers:view" },
      { href: "/contacts", label: "Contacts", icon: "users", permission: "customers:view" },
    ],
  },
  {
    label: "Sales",
    items: [
      { href: "/leads", label: "Leads", icon: "funnel", permission: "sales:view" },
      { href: "/sales", label: "Deals", icon: "briefcase", permission: "sales:view" },
    ],
  },
  {
    label: "Marketing",
    items: [
      { href: "/subscribers", label: "Subscribers", icon: "heart", permission: "customers:view" },
      { href: "/campaigns", label: "Campaigns", icon: "mail", permission: "campaigns:view" },
      { href: "/campaigns/templates", label: "Templates", icon: "edit", permission: "campaigns:view", child: true },
      { href: "/campaigns/lists", label: "Audiences", icon: "users", permission: "campaigns:view", child: true },
      { href: "/campaigns/suppressions", label: "Suppressions", icon: "shield", permission: "campaigns:view", child: true },
    ],
  },
  {
    label: "Purchasing",
    items: [{ href: "/suppliers", label: "Suppliers", icon: "truck", permission: "suppliers:view" }],
  },
  {
    label: "Analytics",
    items: [{ href: "/reports", label: "Reports", icon: "chart", permission: "reports:view" }],
  },
  {
    label: "Settings",
    items: [
      { href: "/settings", label: "Settings", icon: "sliders" },
      { href: "/settings/users", label: "Team", icon: "users", permission: "users:manage" },
    ],
  },
];

/**
 * The sidebar while in Settings (as in the shop admin): a way back to the dashboard, then these sections.
 * Adding a settings page = one line here.
 */
export const SETTINGS_NAV: NavGroup[] = [
  {
    label: "Team",
    items: [
      { href: "/settings/users", label: "Users", icon: "users", permission: "users:manage" },
      { href: "/settings/audit", label: "Audit log", icon: "shield", permission: "audit:view" },
    ],
  },
  {
    label: "Lists",
    items: [
      { href: "/settings/types", label: "Types", icon: "sliders", permission: "lookups:manage" },
      { href: "/settings/tags", label: "Tags", icon: "tag", permission: "lookups:manage" },
      { href: "/settings/custom-fields", label: "Custom fields", icon: "edit", permission: "lookups:manage" },
      { href: "/settings/pipelines", label: "Pipelines", icon: "funnel", permission: "lookups:manage" },
    ],
  },
  {
    label: "Support",
    items: [
      { href: "/settings/sla-policies", label: "SLA policies", icon: "alert", permission: "lookups:manage" },
      { href: "/settings/canned-responses", label: "Canned responses", icon: "copy", permission: "lookups:manage" },
      { href: "/settings/business-hours", label: "Business hours", icon: "clock", permission: "settings:manage" },
    ],
  },
  {
    label: "Email",
    items: [
      { href: "/settings/email", label: "Outgoing email", icon: "mail", permission: "settings:manage" },
      { href: "/settings/email-accounts", label: "Email accounts", icon: "inbox", permission: "inbox:manage" },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/settings/integrations", label: "Integrations", icon: "globe", permission: "settings:manage" },
      { href: "/settings/deployments", label: "Deployments", icon: "download", permission: "settings:manage" },
      { href: "/settings/environment", label: "Test mode", icon: "flask", permission: "settings:manage" },
    ],
  },
];

export function inSettings(pathname: string) {
  return pathname === "/settings" || pathname.startsWith("/settings/");
}

const EXTRA_TITLES: Record<string, string> = { "/account": "Your account", "/settings": "Settings", "/customers/new": "Customers", "/customers/import": "Customers" };

export function isActive(pathname: string, href: string) {
  // "/settings" is the overview only; its sections light up their own entries.
  if (href === "/settings") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** The one entry that owns this page: the longest match, so /campaigns/templates lights Templates and not Campaigns. */
export function activeHref(pathname: string, groups: NavGroup[] = [...SETTINGS_NAV, ...NAV]): string | undefined {
  let best: string | undefined;
  for (const group of groups) for (const item of group.items) if (isActive(pathname, item.href) && (!best || item.href.length > best.length)) best = item.href;
  return best;
}

export function titleFor(pathname: string) {
  if (EXTRA_TITLES[pathname]) return EXTRA_TITLES[pathname];
  const href = activeHref(pathname);
  for (const group of [...SETTINGS_NAV, ...NAV]) for (const item of group.items) if (item.href === href) return item.label;
  return "CRM";
}
