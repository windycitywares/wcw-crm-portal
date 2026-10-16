import { AppShell } from "@/components/layout/AppShell";

export default function CrmLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
