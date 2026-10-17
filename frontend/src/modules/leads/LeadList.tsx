"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Select } from "@/components/ui/Field";
import { Pill } from "@/components/ui/Pill";
import { formatDate } from "@/lib/utils";
import { useDirectory } from "@/modules/records/useDirectory";
import { useLookups } from "@/modules/settings/useLookups";
import { leadSubtitle, STATUS_LABEL, STATUS_TONE, WORKFLOW, type Lead, type LeadOpenStatus } from "./api";

/**
 * Leads as a table, newest first (that ordering comes from the API). The name opens the lead; the status
 * is a picker right in the row, so working a list of new leads never needs a dialog.
 */
export function LeadList({
  leads,
  onEdit,
  onConvert,
  onStatusChange,
  canEdit,
  empty,
}: {
  leads: Lead[] | null;
  onEdit: (lead: Lead) => void;
  onConvert?: (lead: Lead) => void;
  onStatusChange?: (lead: Lead, status: LeadOpenStatus) => void;
  canEdit: (lead: Lead) => boolean;
  empty?: string;
}) {
  const { name } = useDirectory();
  const lookups = useLookups();

  const columns: Column<Lead>[] = [
    {
      key: "lead",
      header: "Lead",
      cell: (l) => (
        <button type="button" onClick={() => onEdit(l)} className="max-w-72 text-left font-medium hover:text-accent-strong hover:underline">
          <span className="block truncate">{l.display_name}</span>
          {leadSubtitle(l) && <span className="block truncate text-xs font-normal text-muted">{leadSubtitle(l)}</span>}
        </button>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (l) =>
        l.status !== "converted" && onStatusChange && canEdit(l) ? (
          <Select
            aria-label={`Status of ${l.display_name}`}
            className="w-32 py-1 text-xs"
            value={l.status}
            onChange={(e) => onStatusChange(l, e.target.value as LeadOpenStatus)}
          >
            {WORKFLOW.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </Select>
        ) : (
          <Pill tone={STATUS_TONE[l.status]}>{STATUS_LABEL[l.status]}</Pill>
        ),
    },
    {
      key: "source",
      header: "Source",
      hide: "md",
      cell: (l) => (
        <span className="text-muted">{l.source ? (lookups.find("lead_source", l.source)?.label ?? l.source) : "—"}</span>
      ),
    },
    { key: "owner", header: "Owner", hide: "lg", cell: (l) => <span className="text-muted">{name(l.owner_id)}</span> },
    {
      key: "added",
      header: "Added",
      align: "right",
      hide: "lg",
      cell: (l) => <span className="num text-muted">{formatDate(l.created_at)}</span>,
    },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (l) =>
        l.status === "converted" ? (
          <span className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 text-xs">
            {l.converted_customer_id && (
              <Link href={`/customers/${l.converted_customer_id}`} className="text-accent-strong hover:underline">
                Customer
              </Link>
            )}
            {l.converted_deal_id && (
              <Link href={`/sales?deal=${l.converted_deal_id}`} className="text-accent-strong hover:underline">
                Deal
              </Link>
            )}
          </span>
        ) : onConvert && canEdit(l) ? (
          <Button variant="secondary" size="sm" onClick={() => onConvert(l)}>
            Convert
          </Button>
        ) : null,
    },
  ];

  return <DataTable columns={columns} rows={leads} rowKey={(l) => l.id} caption="Leads" empty={empty} />;
}
