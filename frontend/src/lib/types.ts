export type Role = "admin" | "manager" | "sales" | "support" | "marketing" | "read_only";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  title: string | null;
  phone: string | null;
  timezone: string;
  last_login_at: string | null;
  created_at: string;
}

export interface Me extends User {
  permissions: string[];
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export const ROLE_LABEL: Record<Role, string> = {
  admin: "Admin",
  manager: "Manager",
  sales: "Sales",
  support: "Support",
  marketing: "Marketing",
  read_only: "Read-only",
};
