import type { IconName } from "@/components/ui/Icon";

export interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  /** Hidden unless the user has this permission (the API enforces it again). */
  permission?: string;
  /** Only shown in the settings page's left panel, not in the main sidebar. */
  hidden?: boolean;
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
    label: "Work",
    items: [
      { href: "/tasks", label: "Tasks", icon: "tasks", permission: "tasks:view" },
      { href: "/tickets", label: "Tickets", icon: "ticket", permission: "tickets:view" },
      { href: "/inbox", label: "Inbox", icon: "inbox", permission: "tickets:view" },
      { href: "/leads", label: "Leads", icon: "inbox", permission: "sales:view" },
      { href: "/sales", label: "Sales", icon: "briefcase", permission: "sales:view" },
      { href: "/campaigns", label: "Campaigns", icon: "mail", permission: "campaigns:view" },
      { href: "/suppliers", label: "Suppliers", icon: "briefcase", permission: "suppliers:view" },
      { href: "/reports", label: "Reports", icon: "chart", permission: "reports:view" },
      { href: "/customers", label: "Customers", icon: "customers", permission: "customers:view" },
      { href: "/contacts", label: "Contacts", icon: "customers", permission: "customers:view" },
    ],
  },
  {
    label: "Administration",
    items: [
      { href: "/settings/users", label: "Users", icon: "users", permission: "users:manage", hidden: true },
      { href: "/settings/types", label: "Types", icon: "sliders", permission: "lookups:manage", hidden: true },
      { href: "/settings/tags", label: "Tags", icon: "tag", permission: "lookups:manage", hidden: true },
      { href: "/settings/pipelines", label: "Pipelines", icon: "funnel", permission: "lookups:manage", hidden: true },
      { href: "/settings/custom-fields", label: "Custom fields", icon: "edit", permission: "lookups:manage", hidden: true },
      { href: "/settings/email", label: "Email", icon: "mail", permission: "settings:manage", hidden: true },
      { href: "/settings/email-accounts", label: "Email accounts", icon: "mail", permission: "inbox:manage", hidden: true },
      { href: "/settings/business-hours", label: "Business hours", icon: "clock", permission: "settings:manage", hidden: true },
      { href: "/settings/sla-policies", label: "SLA policies", icon: "alert", permission: "lookups:manage", hidden: true },
      { href: "/settings/canned-responses", label: "Canned responses", icon: "copy", permission: "lookups:manage", hidden: true },
      { href: "/settings/integrations", label: "Integrations", icon: "globe", permission: "settings:manage", hidden: true },
      { href: "/settings/deployments", label: "Deployments", icon: "download", permission: "settings:manage", hidden: true },
      { href: "/settings/audit", label: "Audit log", icon: "shield", permission: "audit:view", hidden: true },
    ],
  },
];

const EXTRA_TITLES: Record<string, string> = { "/account": "Your account", "/settings": "Settings", "/customers/new": "Customers", "/customers/import": "Customers" };

export function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function titleFor(pathname: string) {
  if (EXTRA_TITLES[pathname]) return EXTRA_TITLES[pathname];
  for (const group of NAV) for (const item of group.items) if (isActive(pathname, item.href)) return item.label;
  return "CRM";
}
