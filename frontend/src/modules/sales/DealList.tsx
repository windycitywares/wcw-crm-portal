"use client";

import { DataTable, type Column } from "@/components/ui/DataTable";
import { Pill } from "@/components/ui/Pill";
import { formatDate } from "@/lib/utils";
import { useDirectory } from "@/modules/records/useDirectory";
import { dealStageLabel, money, STATUS_TONE, type Deal } from "./api";

/**
 * Deals as a table, soonest to close first (that ordering comes from the API; undated deals last). The
 * title opens the deal, the same dialog the board uses, so both views work the same way.
 */
export function DealList({ deals, onEdit, empty }: { deals: Deal[] | null; onEdit: (deal: Deal) => void; empty?: string }) {
  const { name } = useDirectory();

  const columns: Column<Deal>[] = [
    {
      key: "title",
      header: "Deal",
      cell: (d) => (
        <button type="button" onClick={() => onEdit(d)} className="max-w-72 text-left font-medium hover:text-accent-strong hover:underline">
          <span className="block truncate">{d.title}</span>
          {d.customer_name && <span className="block truncate text-xs font-normal text-muted">{d.customer_name}</span>}
        </button>
      ),
    },
    { key: "stage", header: "Stage", hide: "sm", cell: (d) => <Pill tone={STATUS_TONE[d.status]}>{dealStageLabel(d)}</Pill> },
    { key: "value", header: "Value", align: "right", cell: (d) => <span className="num">{money(d.value, d.currency)}</span> },
    {
      key: "close",
      header: "Close date",
      align: "right",
      hide: "md",
      cell: (d) => <span className="num text-muted">{formatDate(d.status === "open" ? d.expected_close_on : (d.closed_at ?? d.expected_close_on))}</span>,
    },
    { key: "owner", header: "Owner", hide: "lg", cell: (d) => <span className="text-muted">{name(d.owner_id)}</span> },
  ];

  return <DataTable columns={columns} rows={deals} rowKey={(d) => d.id} caption="Deals" empty={empty} />;
}
