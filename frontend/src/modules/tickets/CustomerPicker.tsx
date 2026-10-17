"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { customersApi, type Customer } from "@/modules/customers/api";

/** Search-and-pick the customer a ticket is about. The chosen one stays visible until you change it. */
export function CustomerPicker({
  value,
  name,
  onChange,
}: {
  value: number | null;
  name: string | null;
  onChange: (customer: { id: number; name: string } | null) => void;
}) {
  const [picking, setPicking] = useState(false);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Customer[] | null>(null);

  useEffect(() => {
    if (!picking) return;
    const query = q.trim();
    const t = setTimeout(() => {
      customersApi
        .list({ q: query || undefined, page_size: 6 })
        .then((page) => setResults(page.items))
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q, picking]);

  if (value != null && !picking) {
    return (
      <div className="flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-sm">{name ?? `Customer #${value}`}</span>
        <Button type="button" variant="secondary" size="sm" onClick={() => setPicking(true)}>
          Change
        </Button>
        <Button type="button" variant="ghost" size="sm" className="text-danger" onClick={() => onChange(null)}>
          Remove
        </Button>
      </div>
    );
  }

  return (
    <div className="relative">
      <Input
        autoFocus
        type="search"
        placeholder="Search customers by name or email…"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setResults(null);
        }}
      />
      {results && (
        <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-[var(--radius-control)] border border-line bg-surface shadow-[0_16px_40px_-24px_rgba(0,0,0,0.4)]">
          {results.length === 0 && <li className="px-3 py-2 text-sm text-muted">No customers match.</li>}
          {results.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                className="block w-full px-3 py-2 text-left text-sm hover:bg-sand focus-visible:outline-2 focus-visible:outline-accent"
                onClick={() => {
                  onChange({ id: c.id, name: c.display_name });
                  setPicking(false);
                  setQ("");
                  setResults(null);
                }}
              >
                {c.display_name}
                {c.email && <span className="text-muted"> · {c.email}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {value != null && (
        <button type="button" className="mt-1.5 text-xs text-muted underline" onClick={() => setPicking(false)}>
          Keep the current customer
        </button>
      )}
    </div>
  );
}
