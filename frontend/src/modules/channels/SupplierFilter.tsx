"use client";

import { useEffect, useState } from "react";
import { Field, Select } from "@/components/ui/Field";
import { accountsApi, type AccountOption } from "@/modules/accounts/api";

let cache: Promise<AccountOption[]> | null = null;
/** Supplier accounts for pickers and filters, fetched once per page load. */
export function loadSuppliers() {
  return (cache ??= accountsApi.options("", "supplier").catch(() => { cache = null; return []; }));
}

export function useSuppliers() {
  const [suppliers, setSuppliers] = useState<AccountOption[]>([]);
  useEffect(() => { let alive = true; void loadSuppliers().then((s) => alive && setSuppliers(s)); return () => { alive = false; }; }, []);
  return suppliers;
}

/** "Supplier" filter: everyone, one supplier account, or listings/orders without one. */
export function SupplierFilter({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const suppliers = useSuppliers();
  return (
    <Field label="Supplier">
      {(p) => (
        <Select {...p} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">All suppliers</option>
          <option value="none">No supplier yet</option>
          {suppliers.map((s) => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
        </Select>
      )}
    </Field>
  );
}
