"use client";

import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { formatDate } from "@/lib/utils";
import type { FieldDef } from "@/modules/settings/api";

export type CustomValues = Record<string, unknown>;

/**
 * Form inputs for a record type's custom fields. Hidden (inactive) fields are skipped; their stored
 * values are kept by the API. `errors` can carry the API's message per key if a form wants it.
 */
export function CustomFieldsEditor({
  defs,
  values,
  onChange,
}: {
  defs: FieldDef[];
  values: CustomValues;
  onChange: (values: CustomValues) => void;
}) {
  const set = (key: string, value: unknown) => onChange({ ...values, [key]: value });
  return (
    <>
      {defs
        .filter((d) => d.is_active)
        .map((d) => {
          const v = values[d.key];
          const label = d.required ? `${d.label} *` : d.label;
          const hint = d.help_text ?? undefined;
          if (d.field_type === "checkbox") {
            return (
              <label key={d.key} className="flex items-start gap-3 text-sm">
                <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-accent)]" checked={v === true} onChange={(e) => set(d.key, e.target.checked)} />
                <span>
                  <span className="font-medium">{d.label}</span>
                  {hint && <span className="block text-xs text-muted">{hint}</span>}
                </span>
              </label>
            );
          }
          if (d.field_type === "multiselect") {
            const selected = Array.isArray(v) ? (v as string[]) : [];
            return (
              <fieldset key={d.key} className="text-sm">
                <legend className="mb-1.5 font-medium">{label}</legend>
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {(d.options ?? []).map((o) => (
                    <label key={o} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        className="size-4 accent-[var(--color-accent)]"
                        checked={selected.includes(o)}
                        onChange={(e) => set(d.key, e.target.checked ? [...selected, o] : selected.filter((x) => x !== o))}
                      />
                      {o}
                    </label>
                  ))}
                </div>
                {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
              </fieldset>
            );
          }
          return (
            <Field key={d.key} label={label} hint={hint}>
              {(p) => {
                const str = v == null ? "" : String(v);
                switch (d.field_type) {
                  case "textarea":
                    return <Textarea {...p} value={str} onChange={(e) => set(d.key, e.target.value)} />;
                  case "select":
                    return (
                      <Select {...p} value={str} onChange={(e) => set(d.key, e.target.value || null)}>
                        <option value="">—</option>
                        {(d.options ?? []).map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </Select>
                    );
                  case "number":
                    return <Input {...p} type="number" step="any" value={str} onChange={(e) => set(d.key, e.target.value === "" ? null : e.target.value)} />;
                  case "date":
                    return <Input {...p} type="date" value={str} onChange={(e) => set(d.key, e.target.value || null)} />;
                  case "email":
                    return <Input {...p} type="email" value={str} onChange={(e) => set(d.key, e.target.value)} />;
                  case "url":
                    return <Input {...p} type="url" value={str} onChange={(e) => set(d.key, e.target.value)} placeholder="https://" />;
                  default:
                    return <Input {...p} value={str} onChange={(e) => set(d.key, e.target.value)} />;
                }
              }}
            </Field>
          );
        })}
    </>
  );
}

/** Read-only list of a record's custom field values (only fields that have a value). */
export function CustomFieldsView({ defs, values }: { defs: FieldDef[]; values: CustomValues }) {
  const shown = defs.filter((d) => values[d.key] != null && values[d.key] !== "" && !(Array.isArray(values[d.key]) && (values[d.key] as unknown[]).length === 0));
  if (shown.length === 0) return null;
  const display = (d: FieldDef, v: unknown) => {
    if (d.field_type === "checkbox") return v ? "Yes" : "No";
    if (d.field_type === "date") return formatDate(`${String(v)}T12:00:00`);
    if (Array.isArray(v)) return v.join(", ");
    if (d.field_type === "url")
      return (
        <a href={String(v)} target="_blank" rel="noopener noreferrer" className="text-accent underline-offset-4 hover:underline">
          {String(v)}
        </a>
      );
    return String(v);
  };
  return (
    <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_minmax(0,1fr)]">
      {shown.map((d) => (
        <div key={d.key} className="contents">
          <dt className="text-muted">{d.label}</dt>
          <dd className="break-words">{display(d, values[d.key])}</dd>
        </div>
      ))}
    </dl>
  );
}
