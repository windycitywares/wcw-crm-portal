"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { customerFilesApi, type ImportResult } from "@/modules/customers/api";
import { errorText } from "@/modules/settings/api";

const FIELD_LABEL: Record<string, string> = {
  first_name: "First name", last_name: "Last name", full_name: "Full name (split)", company: "Company", email: "Email",
  other_emails: "Other emails", phone: "Phone", type: "Customer type", source: "Source", status: "Status", owner: "Owner",
  tags: "Tags", address_line1: "Address line 1", address_line2: "Address line 2", city: "City", state: "State",
  postal_code: "Postal code", country: "Country",
};

function Summary({ r }: { r: ImportResult }) {
  const verb = r.dry_run ? "would be" : "were";
  return (
    <div className="grid gap-4">
      <p role="status" className="text-sm">
        {r.rows} rows: <strong>{r.created}</strong> new customers {verb} added, <strong>{r.updated}</strong> {verb} updated,{" "}
        <strong>{r.skipped}</strong> {verb} skipped{r.errors.length > 0 ? ` (${r.errors.length} with problems, listed below)` : ""}.
      </p>
      <div>
        <h3 className="text-sm font-medium">Columns used</h3>
        <ul className="mt-1 flex flex-wrap gap-2 text-xs">
          {Object.entries(r.columns).map(([header, field]) => (
            <li key={header} className="rounded-full border border-line px-2.5 py-0.5">
              {header} → {FIELD_LABEL[field] ?? field}
            </li>
          ))}
        </ul>
        {r.ignored_columns.length > 0 && <p className="mt-2 text-xs text-muted">Ignored: {r.ignored_columns.join(", ")}</p>}
      </div>
      {r.errors.length > 0 && (
        <div className="relative overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Rows that can&apos;t be imported</caption>
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th scope="col" className="py-2 pr-4 font-medium">Row</th>
                <th scope="col" className="py-2 font-medium">Problem</th>
              </tr>
            </thead>
            <tbody>
              {r.errors.map((e) => (
                <tr key={e.row} className="border-b border-line/60">
                  <td className="py-1.5 pr-4 tabular-nums">{e.row}</td>
                  <td className="py-1.5 text-danger">{e.error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function ImportCustomersPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"skip" | "update">("skip");
  const [check, setCheck] = useState<ImportResult | null>(null);
  const [done, setDone] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!can("data:export")) return <PageHeader title="Import customers" back={{ href: "/customers", label: "Customers" }} description="Only managers and admins can import." />;

  async function run(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const res = await customerFilesApi.import(file, mode, dryRun);
      if (dryRun) setCheck(res);
      else {
        setDone(res);
        setCheck(null);
        toast.push({ title: "Customers imported", description: `${res.created} added, ${res.updated} updated.` });
      }
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Import customers"
        back={{ href: "/customers", label: "Customers" }}
        description="From a CSV or Excel file (first sheet), up to 5,000 rows. Check the file first; nothing changes until you import."
      />
      <div className="grid max-w-3xl gap-6">
        <Panel>
          <PanelHeader title="1. Choose the file" />
          <PanelBody className="grid gap-4">
            <p className="text-sm text-muted">
              Columns are matched by name (e.g. Name or First name/Last name, Email, Company, Phone, Type, Source, Owner, Tags, City, Zip).
              Types and sources must exist in Administration → Types. Marketing consent can&apos;t be imported.{" "}
              <button type="button" className="text-accent-strong underline focus-visible:outline-2 focus-visible:outline-accent" onClick={() => void customerFilesApi.template().catch((e) => setError(errorText(e)))}>
                Download a template
              </button>
              .
            </p>
            <div className="grid gap-1.5">
              <label htmlFor="import-file" className="text-sm font-medium">
                File
              </label>
              <input
                id="import-file"
                type="file"
                accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="text-sm file:mr-3 file:rounded-[var(--radius-control)] file:border file:border-ink/25 file:bg-transparent file:px-3 file:py-1.5 focus-visible:outline-2 focus-visible:outline-accent"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  setCheck(null);
                  setDone(null);
                }}
              />
            </div>
            <fieldset className="grid gap-2">
              <legend className="mb-1 text-sm font-medium">When the email already belongs to a customer</legend>
              {(
                [
                  ["skip", "Leave that customer as it is"],
                  ["update", "Update that customer with the file's values (empty cells change nothing)"],
                ] as const
              ).map(([value, label]) => (
                <label key={value} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="mode"
                    value={value}
                    checked={mode === value}
                    onChange={() => {
                      setMode(value);
                      setCheck(null);
                    }}
                    className="size-4 accent-[var(--color-accent)] focus-visible:outline-2 focus-visible:outline-accent"
                  />
                  {label}
                </label>
              ))}
            </fieldset>
            {error && (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            )}
            <div>
              <Button size="sm" variant="secondary" disabled={!file || busy} onClick={() => void run(true)}>
                {busy && !check ? "Checking…" : "Check file"}
              </Button>
            </div>
          </PanelBody>
        </Panel>

        {check && (
          <Panel>
            <PanelHeader title="2. Check the result" description="Nothing has been saved yet." />
            <PanelBody className="grid gap-4">
              <Summary r={check} />
              <div>
                <Button size="sm" disabled={busy || check.created + check.updated === 0} onClick={() => void run(false)}>
                  {busy ? "Importing…" : `Import ${check.created + check.updated} customers`}
                </Button>
              </div>
            </PanelBody>
          </Panel>
        )}

        {done && (
          <Panel>
            <PanelHeader title="Imported" />
            <PanelBody className="grid gap-4">
              <Summary r={done} />
              <Link href="/customers" className="text-sm text-accent-strong underline">
                Back to customers
              </Link>
            </PanelBody>
          </Panel>
        )}
      </div>
    </>
  );
}
