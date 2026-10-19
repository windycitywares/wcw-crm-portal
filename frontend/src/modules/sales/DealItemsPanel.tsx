"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import { money, salesApi, type DealItem, type DealItems, type Money, type ShopProduct } from "./api";

/**
 * The products on a deal: what is being quoted, at what price. The lines add up to their own total,
 * which sits next to the deal's value — the value is what the salesperson is asking for, and the
 * button offers to line the two up rather than silently doing it.
 */

interface Fields {
  name: string;
  sku: string;
  quantity: string;
  unit_price: string;
}

/** The editable text of one line (what an input holds, so 2.00 shows as 2). */
function fields(item: DealItem): Fields {
  return {
    name: item.name,
    sku: item.sku ?? "",
    quantity: String(Number(item.quantity)),
    unit_price: String(Number(item.unit_price)),
  };
}

const INPUT =
  "min-w-0 rounded-md bg-transparent px-1.5 py-1 text-sm placeholder:text-muted/70 hover:bg-sand " +
  "focus-visible:bg-surface focus-visible:outline focus-visible:outline-1 focus-visible:outline-accent";

/** A blank line. `shop_product_id` says the line came from the catalog (set by the picker). */
function emptyDraft() {
  return { name: "", sku: "", quantity: "1", unit_price: "", shop_product_id: null as number | null };
}

/** One line, edited where it sits: fix what's wrong and save, or take it off the deal. */
function LineRow({
  dealId,
  item,
  currency,
  canEdit,
  onChanged,
}: {
  dealId: number;
  item: DealItem;
  currency: string;
  canEdit: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState<Fields>(() => fields(item));
  const [busy, setBusy] = useState(false);

  useEffect(() => setForm(fields(item)), [item]);

  const set = (key: keyof Fields, value: string) => setForm((f) => ({ ...f, [key]: value }));
  const dirty = JSON.stringify(form) !== JSON.stringify(fields(item));

  async function save() {
    if (!form.name.trim()) {
      toast.push({ tone: "danger", title: "Give the line a name" });
      return;
    }
    setBusy(true);
    try {
      await salesApi.updateDealItem(dealId, item.id, {
        name: form.name.trim(),
        sku: form.sku.trim() || null,
        quantity: form.quantity.trim() || "1",
        unit_price: form.unit_price.trim() || "0",
      });
      onChanged();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't save the line", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await salesApi.removeDealItem(dealId, item.id);
      toast.push({ title: "Line removed", description: item.name });
      onChanged();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't remove the line", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  const enter = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void save();
    }
  };

  if (!canEdit) {
    return (
      <li className="flex flex-wrap items-center gap-x-2 px-1.5 py-1 text-sm">
        <span className="min-w-0 flex-1 truncate">{item.name}</span>
        {item.sku && <span className="text-xs text-muted">{item.sku}</span>}
        <span className="num text-right text-xs text-muted">
          {Number(item.quantity)} × {money(item.unit_price, currency)}
        </span>
        <span className="num w-24 text-right">{money(item.total, currency)}</span>
      </li>
    );
  }

  return (
    <li className="flex flex-wrap items-center gap-1">
      <input
        aria-label="Product"
        className={cn(INPUT, "flex-1 basis-40")}
        value={form.name}
        onChange={(e) => set("name", e.target.value)}
        onKeyDown={enter}
      />
      <input
        aria-label="SKU"
        placeholder="SKU"
        className={cn(INPUT, "w-20")}
        value={form.sku}
        onChange={(e) => set("sku", e.target.value)}
        onKeyDown={enter}
      />
      <input
        aria-label="Quantity"
        type="number"
        min="0"
        step="0.01"
        className={cn(INPUT, "num w-20 text-right")}
        value={form.quantity}
        onChange={(e) => set("quantity", e.target.value)}
        onKeyDown={enter}
      />
      <span className="text-xs text-muted">×</span>
      <input
        aria-label="Unit price"
        type="number"
        min="0"
        step="0.01"
        className={cn(INPUT, "num w-24 text-right")}
        value={form.unit_price}
        onChange={(e) => set("unit_price", e.target.value)}
        onKeyDown={enter}
      />
      <span className="num w-24 text-right text-sm font-medium">{money(item.total, currency)}</span>
      {dirty ? (
        <Button size="sm" variant="secondary" disabled={busy} onClick={() => void save()}>
          Save
        </Button>
      ) : (
        <button
          type="button"
          aria-label={`Remove ${item.name}`}
          title="Remove the line"
          disabled={busy}
          onClick={() => void remove()}
          className="rounded-md p-1.5 text-muted hover:bg-sand hover:text-danger"
        >
          <Icon name="trash" className="size-4" />
        </button>
      )}
    </li>
  );
}

export function DealItemsPanel({
  dealId,
  currency,
  dealValue,
  canEdit,
  onUseTotal,
}: {
  dealId: number;
  currency: string;
  dealValue: Money;
  canEdit: boolean;
  /** Called with the lines total when someone asks for the deal's value to become it. */
  onUseTotal: (total: number) => void;
}) {
  const toast = useToast();
  const [data, setData] = useState<DealItems | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState(emptyDraft);
  const [busy, setBusy] = useState(false);
  const [shopQuery, setShopQuery] = useState("");
  const [shopResults, setShopResults] = useState<ShopProduct[] | null>(null);
  const [shopBusy, setShopBusy] = useState(false);
  const [shopError, setShopError] = useState<string | null>(null);

  // The catalog picker: two characters and a pause, so a fast typist sends one request, not one per key.
  useEffect(() => {
    const q = shopQuery.trim();
    if (!adding || q.length < 2) {
      setShopResults(null);
      setShopError(null);
      setShopBusy(false);
      return;
    }
    let live = true;
    setShopBusy(true);
    const timer = setTimeout(() => {
      salesApi
        .shopProducts(q)
        .then((rows) => {
          if (live) {
            setShopResults(rows);
            setShopError(null);
          }
        })
        .catch((err) => {
          if (live) {
            setShopResults([]); // the manual fields below still work
            setShopError(err instanceof Error ? err.message : "Couldn't search the shop");
          }
        })
        .finally(() => {
          if (live) setShopBusy(false);
        });
    }, 250);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [adding, shopQuery]);

  const load = useCallback(async () => {
    try {
      setData(await salesApi.dealItems(dealId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load the lines");
    }
  }, [dealId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function add() {
    if (!draft.name.trim()) {
      toast.push({ tone: "danger", title: "Give the line a name" });
      return;
    }
    setBusy(true);
    try {
      await salesApi.addDealItem(dealId, {
        name: draft.name.trim(),
        sku: draft.sku.trim() || null,
        shop_product_id: draft.shop_product_id,
        quantity: draft.quantity.trim() || "1",
        unit_price: draft.unit_price.trim() || "0",
      });
      setDraft(emptyDraft());
      setShopQuery("");
      setShopResults(null);
      setAdding(false);
      await load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't add the line", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  const lines = Number(data?.total ?? 0);
  const value = Number(dealValue) || 0;
  const matches = Math.abs(lines - value) < 0.005;
  const hasLines = (data?.count ?? 0) > 0;

  const set = (key: "name" | "sku" | "quantity" | "unit_price", value: string) =>
    setDraft((d) => ({ ...d, [key]: value }));

  /** Take a catalog row: its name, SKU and base price start the line, and its id travels with it. */
  function pick(product: ShopProduct) {
    setDraft({
      name: product.name,
      sku: product.sku,
      quantity: "1",
      unit_price: String(Number(product.price)),
      shop_product_id: product.id,
    });
    setShopQuery("");
    setShopResults(null);
    setShopError(null);
  }

  return (
    <section aria-label="Products on this deal">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="text-sm font-medium text-ink">
          Products on this deal {data && <span className="font-normal text-muted">· {data.count}</span>}
        </p>
        {hasLines && (
          <p className="text-sm text-muted">
            Lines <span className="num text-ink">{money(lines, currency)}</span> · Deal value{" "}
            <span className="num text-ink">{money(value, currency)}</span>
          </p>
        )}
      </div>

      {error && (
        <p role="alert" className="mb-2 text-sm text-danger">
          {error}
        </p>
      )}

      {hasLines && canEdit && (
        <p className="mb-2 text-xs text-muted">
          {matches ? (
            "The lines add up to the deal value."
          ) : (
            <>
              The lines and the deal value differ.{" "}
              <button type="button" onClick={() => onUseTotal(lines)} className="text-accent-strong underline">
                Use {money(lines, currency)} as the deal value
              </button>{" "}
              (then save the deal).
            </>
          )}
        </p>
      )}

      {data === null ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : data.items.length === 0 && !adding ? (
        <p className="text-sm text-muted">
          Nothing on this deal yet{canEdit ? " — add the products that make it up." : "."}
        </p>
      ) : (
        <ul className="grid gap-0.5">
          {data.items.map((item) => (
            <LineRow key={item.id} dealId={dealId} item={item} currency={currency} canEdit={canEdit} onChanged={() => void load()} />
          ))}
        </ul>
      )}

      {canEdit &&
        (adding ? (
          <div className="mt-2 flex flex-wrap items-center gap-1 border-t border-line pt-2">
            <div className="w-full">
              <input
                aria-label="Search the shop catalog"
                placeholder="Search the shop catalog…"
                className={cn(INPUT, "w-full border border-line")}
                value={shopQuery}
                onChange={(e) => setShopQuery(e.target.value)}
                autoFocus
              />
              {shopError && (
                <p role="alert" className="mt-1 text-xs text-danger">
                  {shopError}
                </p>
              )}
              {shopBusy && <p className="mt-1 text-xs text-muted">Searching…</p>}
              {shopResults && shopResults.length > 0 && (
                <ul aria-label="Shop catalog matches" className="mt-1 max-h-48 overflow-y-auto rounded-md border border-line">
                  {shopResults.map((product) => (
                    <li key={product.id}>
                      <button
                        type="button"
                        onClick={() => pick(product)}
                        className="flex w-full items-baseline justify-between gap-2 px-2 py-1 text-left text-sm hover:bg-sand focus-visible:bg-sand"
                      >
                        <span className="min-w-0 truncate">
                          {product.name}
                          <span className="ml-2 text-xs text-muted">{product.sku}</span>
                        </span>
                        <span className="num shrink-0 text-xs text-muted">{money(product.price, product.currency)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {shopResults && shopResults.length === 0 && !shopBusy && !shopError && (
                <p className="mt-1 text-xs text-muted">Nothing in the shop matches “{shopQuery.trim()}”.</p>
              )}
            </div>
            <input
              aria-label="Product"
              placeholder="Product or service"
              className={cn(INPUT, "flex-1 basis-40 border border-line")}
              value={draft.name}
              onChange={(e) => set("name", e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void add();
                }
              }}
            />
            <input
              aria-label="SKU"
              placeholder="SKU"
              className={cn(INPUT, "w-20 border border-line")}
              value={draft.sku}
              onChange={(e) => set("sku", e.target.value)}
            />
            <input
              aria-label="Quantity"
              type="number"
              min="0"
              step="0.01"
              className={cn(INPUT, "num w-20 border border-line text-right")}
              value={draft.quantity}
              onChange={(e) => set("quantity", e.target.value)}
            />
            <input
              aria-label="Unit price"
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              className={cn(INPUT, "num w-24 border border-line text-right")}
              value={draft.unit_price}
              onChange={(e) => set("unit_price", e.target.value)}
            />
            <Button size="sm" disabled={busy} onClick={() => void add()}>
              {busy ? "Adding…" : "Add"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setAdding(false);
                setDraft(emptyDraft());
                setShopQuery("");
                setShopResults(null);
                setShopError(null);
              }}
            >
              Cancel
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="secondary" className="mt-2" onClick={() => setAdding(true)}>
            <Icon name="plus" className="size-4" />
            Add a line
          </Button>
        ))}
    </section>
  );
}
