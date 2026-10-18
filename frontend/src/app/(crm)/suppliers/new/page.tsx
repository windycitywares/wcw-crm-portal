"use client";

import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth";
import { SupplierForm } from "@/modules/suppliers/SupplierForm";

export default function NewSupplierPage() {
  const router = useRouter();
  const { can } = useAuth();
  if (!can("suppliers:edit")) return <PageHeader title="New supplier" description="You don't have permission to add suppliers." back={{ href: "/suppliers", label: "Suppliers" }} />;

  return (
    <>
      <PageHeader title="New supplier" back={{ href: "/suppliers", label: "Suppliers" }} />
      <SupplierForm supplier={null} onSaved={(supplier) => router.push(`/suppliers/${supplier.id}`)} />
    </>
  );
}