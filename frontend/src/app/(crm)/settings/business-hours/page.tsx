"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/utils";
import { errorText, settingsApi, type BusinessHours, type Day } from "@/modules/settings/api";

const DAYS: { key: Day; label: string }[] = [
  { key: "mon", label: "Monday" },
  { key: "tue", label: "Tuesday" },
  { key: "wed", label: "Wednesday" },
  { key: "thu", label: "Thursday" },
  { key: "fri", label: "Friday" },
  { key: "sat", label: "Saturday" },
  { key: "sun", label: "Sunday" },
];

export default function BusinessHoursPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState<BusinessHours | null>(null);
  const [holiday, setHoliday] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const allowed = can("settings:manage");

  useEffect(() => {
    if (!allowed) return;
    settingsApi
      .get<BusinessHours>("business_hours")
      .then(({ values }) => setForm(values))
      .catch((err) => toast.push({ tone: "danger", title: "Couldn't load business hours", description: errorText(err) }));
  }, [allowed, toast]);

  if (!allowed) return <PageHeader title="Business hours" description="Only admins can change business hours." />;
  if (!form) return <PageHeader title="Business hours" description="Loading…" />;

  const setDay = (day: Day, value: { open: string; close: string } | null) => setForm({ ...form, days: { ...form.days, [day]: value } });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      setForm((await settingsApi.save<BusinessHours>("business_hours", { ...form })).values);
      toast.push({ title: "Business hours saved" });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Business hours" description="Used for support response-time targets: the clock only runs while you're open." />
      <form onSubmit={save} className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-2">
        {error && (
          <p role="alert" className="rounded-[var(--radius-control)] border border-danger/30 bg-danger/8 px-3 py-2 text-sm text-danger xl:col-span-2">
            {error}
          </p>
        )}
        <Panel>
          <PanelHeader title="Opening hours" />
          <PanelBody className="grid gap-3">
            <Field label="Time zone" hint="e.g. America/Chicago" className="max-w-xs">
              {(p) => <Input {...p} value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />}
            </Field>
            <table className="text-sm">
              <caption className="sr-only">Opening hours per day</caption>
              <thead className="text-left text-xs text-muted">
                <tr>
                  <th scope="col" className="py-2 font-medium">
                    Day
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    Open
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    From
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    To
                  </th>
                </tr>
              </thead>
              <tbody>
                {DAYS.map(({ key, label }) => {
                  const hours = form.days[key];
                  return (
                    <tr key={key}>
                      <th scope="row" className="py-1.5 pr-3 text-left font-medium">
                        {label}
                      </th>
                      <td className="py-1.5 pr-3">
                        <input
                          type="checkbox"
                          aria-label={`Open on ${label}`}
                          className="size-4 accent-[var(--color-accent)]"
                          checked={!!hours}
                          onChange={(e) => setDay(key, e.target.checked ? { open: "09:00", close: "17:00" } : null)}
                        />
                      </td>
                      <td className="py-1.5 pr-3">
                        {hours && (
                          <Input
                            type="time"
                            aria-label={`${label} opening time`}
                            className="w-32 py-1.5"
                            value={hours.open}
                            onChange={(e) => setDay(key, { ...hours, open: e.target.value })}
                          />
                        )}
                      </td>
                      <td className="py-1.5">
                        {hours ? (
                          <Input
                            type="time"
                            aria-label={`${label} closing time`}
                            className="w-32 py-1.5"
                            value={hours.close}
                            onChange={(e) => setDay(key, { ...hours, close: e.target.value })}
                          />
                        ) : (
                          <span className="text-muted">Closed</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Holidays" description="Closed all day." />
          <PanelBody className="grid gap-3">
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Date">{(p) => <Input {...p} type="date" value={holiday} onChange={(e) => setHoliday(e.target.value)} />}</Field>
              <Button
                size="sm"
                variant="secondary"
                disabled={!holiday || form.holidays.includes(holiday)}
                onClick={() => {
                  setForm({ ...form, holidays: [...form.holidays, holiday].sort() });
                  setHoliday("");
                }}
              >
                <Icon name="plus" className="size-4" />
                Add holiday
              </Button>
            </div>
            <ul className="divide-y divide-line">
              {form.holidays.map((d) => (
                <li key={d} className="flex items-center justify-between py-2 text-sm">
                  {formatDate(`${d}T12:00:00`)}
                  <Button size="sm" variant="ghost" onClick={() => setForm({ ...form, holidays: form.holidays.filter((h) => h !== d) })}>
                    <Icon name="close" className="size-4" />
                    Remove<span className="sr-only"> {d}</span>
                  </Button>
                </li>
              ))}
              {form.holidays.length === 0 && <li className="py-2 text-sm text-muted">No holidays added.</li>}
            </ul>
          </PanelBody>
        </Panel>
        <div className="xl:col-span-2">
          <Button type="submit" size="sm" disabled={busy}>
            {busy ? "Saving…" : "Save business hours"}
          </Button>
        </div>
      </form>
    </>
  );
}
