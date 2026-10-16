import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const dateTime = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" });
const dateOnly = new Intl.DateTimeFormat("en-US", { dateStyle: "medium" });

export function formatDateTime(value: string | null | undefined) {
  return value ? dateTime.format(new Date(value)) : "—";
}

export function formatDate(value: string | null | undefined) {
  return value ? dateOnly.format(new Date(value)) : "—";
}

/** "Mia Marketing" → "MM"; falls back to the first letter of the email. */
export function initials(name: string | null | undefined, email: string) {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return email.slice(0, 1).toUpperCase();
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}
