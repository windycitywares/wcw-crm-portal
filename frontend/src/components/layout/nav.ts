import type { IconName } from "@/components/ui/Icon";

export interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  /** Hidden unless the user has this permission (the API enforces it again). */
  permission?: string;
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
    items: [{ href: "/customers", label: "Customers", icon: "customers", permission: "customers:view" }],
  },
  {
    label: "Administration",
    items: [
      { href: "/settings/users", label: "Users", icon: "users", permission: "users:manage" },
      { href: "/settings/types", label: "Types", icon: "sliders", permission: "lookups:manage" },
      { href: "/settings/tags", label: "Tags", icon: "tag", permission: "lookups:manage" },
      { href: "/settings/custom-fields", label: "Custom fields", icon: "edit", permission: "lookups:manage" },
      { href: "/settings/email", label: "Email", icon: "mail", permission: "settings:manage" },
      { href: "/settings/business-hours", label: "Business hours", icon: "clock", permission: "settings:manage" },
      { href: "/settings/deployments", label: "Deployments", icon: "download", permission: "settings:manage" },
      { href: "/settings/audit", label: "Audit log", icon: "shield", permission: "audit:view" },
    ],
  },
];

const EXTRA_TITLES: Record<string, string> = { "/account": "Your account", "/customers/new": "Customers" };

export function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function titleFor(pathname: string) {
  if (EXTRA_TITLES[pathname]) return EXTRA_TITLES[pathname];
  for (const group of NAV) for (const item of group.items) if (isActive(pathname, item.href)) return item.label;
  return "CRM";
}
