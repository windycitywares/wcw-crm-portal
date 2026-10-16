"use client";

import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/ui/PageHeader";
import { useToast } from "@/components/ui/Toast";
import { CustomerForm } from "@/modules/customers/CustomerForm";

export default function NewCustomerPage() {
  const router = useRouter();
  const toast = useToast();
  return (
    <>
      <PageHeader title="Add customer" back={{ href: "/customers", label: "Customers" }} />
      <div className="max-w-3xl">
        <CustomerForm
          customer={null}
          onSaved={(c) => {
            toast.push({ title: "Customer added", description: c.display_name });
            router.push(`/customers/${c.id}`);
          }}
        />
      </div>
    </>
  );
}
