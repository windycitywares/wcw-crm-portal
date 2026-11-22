"use client";

import { useEffect, useState } from "react";
import { Field, Input, Select } from "@/components/ui/Field";
import { accountsApi, type AccountOption } from "./api";

/** Pick an account by typing part of its name. `type` narrows it, e.g. "supplier" for "select supplier". */
export function AccountPicker({ label = "Account", value, currentName, type, onChange, className }: {
  label?: string;
  value: number | null;
  currentName?: string | null;
  type?: string;
  onChange: (id: number | null, name: string | null) => void;
  className?: string;
}) {
  const [q, setQ] = useState("");
  const [options, setOptions] = useState<AccountOption[]>([]);

  useEffect(() => {
    let alive = true;
    const t = setTimeout(() => {
      void accountsApi.options(q, type ?? "").then((rows) => alive && setOptions(rows)).catch(() => alive && setOptions([]));
    }, 250);
    return () => { alive = false; clearTimeout(t); };
  }, [q, type]);

  const list = value !== null && !options.some((o) => o.id === value)
    ? [{ id: value, name: currentName ?? `Account #${value}`, account_type: type ?? "" }, ...options]
    : options;

  return (
    <div className={className}>
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Field label={`Find ${label.toLowerCase()}`}>
          {(p) => <Input {...p} type="search" placeholder="Type a name" value={q} onChange={(e) => setQ(e.target.value)} />}
        </Field>
        <Field label={label}>
          {(p) => (
            <Select {...p} value={value ?? ""} onChange={(e) => {
              const id = e.target.value ? Number(e.target.value) : null;
              onChange(id, list.find((o) => o.id === id)?.name ?? null);
            }}>
              <option value="">None</option>
              {list.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </Select>
          )}
        </Field>
      </div>
    </div>
  );
}
