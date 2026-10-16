"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { useToast } from "@/components/ui/Toast";
import { customersApi, type Customer } from "@/modules/customers/api";
import { CustomerForm } from "@/modules/customers/CustomerForm";

export default function EditCustomerPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    customersApi
      .get(Number(id))
      .then(setCustomer)
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load the customer"));
  }, [id]);

  return (
    <>
      <PageHeader title={customer ? `Edit ${customer.display_name}` : "Edit customer"} back={{ href: `/customers/${id}`, label: customer?.display_name ?? "Customer" }} />
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {!customer && !error && <p className="text-sm text-muted">Loading…</p>}
      {customer && (
        <div className="max-w-3xl">
          <CustomerForm
            customer={customer}
            onSaved={(c) => {
              toast.push({ title: "Customer saved", description: c.display_name });
              router.push(`/customers/${c.id}`);
            }}
          />
        </div>
      )}
    </>
  );
}
