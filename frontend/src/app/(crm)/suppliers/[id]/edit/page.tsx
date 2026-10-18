"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth";
import { suppliersApi, type Supplier } from "@/modules/suppliers/api";
import { SupplierForm } from "@/modules/suppliers/SupplierForm";

export default function EditSupplierPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { can } = useAuth();
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const supplierId = Number(id);
    if (!Number.isSafeInteger(supplierId) || supplierId < 1) {
      setError("Supplier not found.");
      return;
    }
    void suppliersApi.get(supplierId).then(setSupplier).catch((err: unknown) => {
      setError(err instanceof Error ? err.message : "Couldn't load supplier");
    });
  }, [id]);

  if (!can("suppliers:edit")) return <PageHeader title="Edit supplier" description="You don't have permission to edit suppliers." back={{ href: "/suppliers", label: "Suppliers" }} />;
  if (error) return <PageHeader title="Edit supplier" description={error} back={{ href: "/suppliers", label: "Suppliers" }} />;
  if (!supplier) return <p className="text-sm text-muted">Loading supplier…</p>;

  return (
    <>
      <PageHeader title={`Edit ${supplier.name}`} back={{ href: `/suppliers/${supplier.id}`, label: "Supplier" }} />
      <SupplierForm supplier={supplier} onSaved={() => router.push(`/suppliers/${supplier.id}`)} />
    </>
  );
}