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
      { href: "/accounts", label: "Accounts", icon: "briefcase", permission: "customers:view" },
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
/** What a supplier's login sees: only their own orders and payments. */
export const SUPPLIER_NAV: NavGroup[] = [
  {
    label: "Your work",
    items: [
      { href: "/supplier", label: "Your orders", icon: "orders", permission: "supplier:portal" },
      { href: "/supplier/payments", label: "Your payments", icon: "archive", permission: "supplier:portal" },
    ],
  },
];

/** What each connected sales channel adds under "External shops" (the group only shows connected ones). */
export const CHANNEL_NAV: Record<string, NavItem[]> = {
  etsy: [
    { href: "/channels/etsy", label: "Etsy", icon: "cart", permission: "channels:view" },
    { href: "/channels/etsy/orders", label: "Orders", icon: "orders", permission: "channels:view", child: true },
    { href: "/channels/etsy/listings", label: "Listings", icon: "tag", permission: "channels:view", child: true },
    { href: "/channels/etsy/payments", label: "Supplier payments", icon: "archive", permission: "channels:view", child: true },
  ],
};

/** The sidebar with an "External shops" group (after Sales) for the connected channels. */
export function withChannels(nav: NavGroup[], connected: string[]): NavGroup[] {
  const items = connected.flatMap((key) => CHANNEL_NAV[key] ?? []);
  if (!items.length) return nav;
  const at = nav.findIndex((g) => g.label === "Sales");
  const group: NavGroup = { label: "External shops", items };
  return at < 0 ? [...nav, group] : [...nav.slice(0, at + 1), group, ...nav.slice(at + 1)];
}

export const SETTINGS_NAV: NavGroup[] = [
  {
    label: "Team",
    items: [
      { href: "/settings/users", label: "Users", icon: "users", permission: "users:manage" },
      { href: "/settings/supplier-logins", label: "Supplier logins", icon: "key", permission: "users:manage" },
      { href: "/settings/audit", label: "Audit log", icon: "shield", permission: "audit:view" },
      { href: "/settings/trash", label: "Trash", icon: "trash", permission: "trash:manage" },
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
      { href: "/settings/channels", label: "Sales channels", icon: "cart", permission: "channels:manage" },
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
const CHANNEL_GROUP: NavGroup = { items: [...Object.values(CHANNEL_NAV).flat(), ...SUPPLIER_NAV[0].items] };

export function activeHref(pathname: string, groups: NavGroup[] = [...SETTINGS_NAV, ...NAV, CHANNEL_GROUP]): string | undefined {
  let best: string | undefined;
  for (const group of groups) for (const item of group.items) if (isActive(pathname, item.href) && (!best || item.href.length > best.length)) best = item.href;
  return best;
}

export function titleFor(pathname: string) {
  if (EXTRA_TITLES[pathname]) return EXTRA_TITLES[pathname];
  const href = activeHref(pathname);
  for (const group of [...SETTINGS_NAV, ...NAV, CHANNEL_GROUP]) for (const item of group.items) if (item.href === href) return item.label;
  return "CRM";
}
