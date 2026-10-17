"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { campaignsApi, type AudienceMember, type SegmentField, type SegmentRule, type SegmentRules, type TargetList } from "@/modules/campaigns/api";
import { useDirectory } from "@/modules/records/useDirectory";
import { tagsApi, type Tag } from "@/modules/settings/api";
import { useLookups } from "@/modules/settings/useLookups";

type RuleDraft = { field: string; op: string; value: string | string[] };
type ListForm = { name: string; description: string; kind: "static" | "segment" };

const STATUSES = ["active", "inactive", "blocked"];
const selectClass = "h-9 w-full rounded border border-line bg-canvas px-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent";

function blankRule(fields: SegmentField[]): RuleDraft {
  const first = fields[0];
  return { field: first?.field ?? "", op: first?.ops[0]?.op ?? "", value: "" };
}

function draftRules(rules: SegmentRules | null, fields: SegmentField[]): RuleDraft[] {
  if (!rules?.rules.length) return [blankRule(fields)];
  return rules.rules.map((rule) => ({
    field: rule.field,
    op: rule.op,
    value: Array.isArray(rule.value) ? rule.value.map(String) : rule.value == null ? "" : String(rule.value),
  }));
}

function buildRules(match: "all" | "any", drafts: RuleDraft[], fields: SegmentField[]): SegmentRules {
  const rules: SegmentRule[] = drafts.map((draft) => {
    const field = fields.find((item) => item.field === draft.field);
    const op = field?.ops.find((item) => item.op === draft.op)?.op ?? draft.op;
    let value: unknown = draft.value;
    if (op === "none" || op === "never") value = null;
    else if (field?.value_kind === "tags" || field?.value_kind === "users") {
      value = (Array.isArray(draft.value) ? draft.value : [draft.value]).map(Number);
    } else if (field?.value_kind === "customer_type" || field?.value_kind === "lead_source") {
      value = Array.isArray(draft.value) ? draft.value : [draft.value];
    } else if (field?.value_kind === "yesno") value = draft.value === "true";
    else if (field?.value_kind === "number" || field?.value_kind === "money" || field?.value_kind === "days") value = Number(draft.value);
    return { field: draft.field, op, value };
  });
  return { match, rules };
}

export default function CampaignListsPage() {
  const { can } = useAuth();
  const lookups = useLookups();
  const directory = useDirectory();
  const [data, setData] = useState<Page<TargetList> | null>(null);
  const [fields, setFields] = useState<SegmentField[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [form, setForm] = useState<ListForm>({ name: "", description: "", kind: "static" });
  const [draft, setDraft] = useState<RuleDraft[]>([]);
  const [match, setMatch] = useState<"all" | "any">("all");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [previewId, setPreviewId] = useState<number | null>(null);
  const [preview, setPreview] = useState<Page<AudienceMember> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const canEdit = can("campaigns:edit");

  const load = async () => {
    try {
      const [lists, vocabulary, availableTags] = await Promise.all([
        campaignsApi.lists.list(),
        campaignsApi.segmentFields(),
        tagsApi.search(),
      ]);
      setData(lists);
      setFields(vocabulary);
      setTags(availableTags);
      setDraft((current) => current.length ? current : [blankRule(vocabulary)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load audiences");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canEdit || !form.name.trim() || (form.kind === "segment" && !rulesReady)) return;
    setBusy(true);
    setError(null);
    try {
      const details = { name: form.name.trim(), description: form.description.trim() || null };
      if (editingId) {
        await campaignsApi.lists.update(editingId, {
          ...details,
          rules: buildRules(match, draft, fields),
        });
      } else {
        await campaignsApi.lists.create({
          ...details,
          kind: form.kind,
          rules: form.kind === "segment" ? buildRules(match, draft, fields) : null,
        });
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the audience");
    } finally {
      setBusy(false);
    }
  };

  const resetForm = () => {
    setForm({ name: "", description: "", kind: "static" });
    setDraft([blankRule(fields)]);
    setMatch("all");
    setEditingId(null);
  };

  const editSegment = (list: TargetList) => {
    setEditingId(list.id);
    setForm({ name: list.name, description: list.description ?? "", kind: "segment" });
    setDraft(draftRules(list.rules, fields));
    setMatch(list.rules?.match ?? "all");
    setPreviewId(null);
    setPreview(null);
  };

  const previewSegment = async (id: number) => {
    setError(null);
    try {
      const rows = await campaignsApi.lists.members(id);
      setPreviewId(id);
      setPreview(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't preview matching customers");
    }
  };

  const changeField = (index: number, fieldName: string) => {
    const field = fields.find((item) => item.field === fieldName);
    setDraft((current) => current.map((rule, i) => i === index
      ? { field: fieldName, op: field?.ops[0]?.op ?? "", value: field?.value_kind === "tags" || field?.value_kind === "users" || field?.value_kind === "customer_type" || field?.value_kind === "lead_source" ? [] : "" }
      : rule));
  };

  const rulesReady = draft.length > 0 && draft.every((rule) => {
    const field = fields.find((item) => item.field === rule.field);
    if (!field || !field.ops.some((item) => item.op === rule.op)) return false;
    if (rule.op === "none" || rule.op === "never") return true;
    return Array.isArray(rule.value) ? rule.value.length > 0 : rule.value.trim() !== "";
  });

  const remove = async (id: number) => {
    if (!canEdit || !confirm("Delete this audience?")) return;
    try {
      await campaignsApi.lists.remove(id);
      if (previewId === id) {
        setPreviewId(null);
        setPreview(null);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't delete the audience");
    }
  };

  return (
    <>
      <PageHeader title="Campaign audiences" description="Static lists and live rule-based segments for each campaign." back={{ href: "/campaigns", label: "Campaigns" }} />

      {error && <div className="mb-4 rounded border border-danger/50 bg-danger/8 px-3 py-2 text-sm text-danger">{error}</div>}

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Panel>
          <PanelHeader title="Existing audiences" description="A campaign copies the audience when it starts." />
          <PanelBody className="space-y-3">
            {data?.items.length ? (
              data.items.map((list) => (
                <div key={list.id} className="flex items-center justify-between gap-3 rounded border border-line bg-canvas px-3 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-ink">{list.name}</div>
                    <div className="text-sm text-muted">{list.kind === "segment" ? "Live segment" : "Static list"} · {list.reachable} reachable / {list.members} members</div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    {list.kind === "segment" && (
                      <>
                        <Button variant="secondary" size="sm" onClick={() => void previewSegment(list.id)}>Preview</Button>
                        {canEdit && <Button variant="secondary" size="sm" onClick={() => editSegment(list)}>Edit</Button>}
                      </>
                    )}
                    {canEdit && <Button variant="ghost" size="sm" className="text-danger" onClick={() => void remove(list.id)}>Delete</Button>}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted">No audiences created yet.</p>
            )}
          </PanelBody>
        </Panel>

        {canEdit && (
          <Panel>
            <PanelHeader title={editingId ? "Edit segment" : "New audience"} description={editingId ? "Update the rules that determine who matches." : "Create a static list or define a live segment."} />
            <PanelBody>
              <form onSubmit={submit} className="space-y-4">
                {!editingId && (
                  <div className="flex gap-2" role="group" aria-label="Audience type">
                    {(["static", "segment"] as const).map((kind) => (
                      <Button key={kind} type="button" size="sm" variant={form.kind === kind ? "primary" : "secondary"} aria-pressed={form.kind === kind} onClick={() => setForm((current) => ({ ...current, kind }))}>
                        {kind === "static" ? "Static list" : "Live segment"}
                      </Button>
                    ))}
                  </div>
                )}
                <Field label="Audience name">
                  {(p) => <Input {...p} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />}
                </Field>

                <Field label="Description" hint="Optional context for the team.">
                  {(p) => <Textarea {...p} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} className="min-h-[120px]" />}
                </Field>

                {form.kind === "segment" && (
                  <section className="space-y-4 border-t border-line pt-4" aria-label="Segment rules">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold">Match customers</h3>
                        <p className="mt-1 text-xs text-muted">Rules are evaluated against current customer data.</p>
                      </div>
                      <label className="flex items-center gap-2 text-sm text-muted">
                        Match
                        <select className={selectClass} value={match} onChange={(e) => setMatch(e.target.value as "all" | "any")}>
                          <option value="all">all rules</option>
                          <option value="any">any rule</option>
                        </select>
                      </label>
                    </div>

                    {draft.map((rule, index) => {
                      const field = fields.find((item) => item.field === rule.field);
                      const noValue = rule.op === "none" || rule.op === "never";
                      const updateValue = (value: string | string[]) => setDraft((current) => current.map((item, i) => i === index ? { ...item, value } : item));
                      return (
                        <div key={`${index}-${rule.field}`} className="grid gap-3 rounded border border-line bg-canvas p-3 md:grid-cols-[1fr_1fr_1.2fr_auto] md:items-end">
                          <Field label="Field">
                            {(p) => <select {...p} className={selectClass} value={rule.field} onChange={(e) => changeField(index, e.target.value)}>
                              {fields.map((item) => <option key={item.field} value={item.field}>{item.label}</option>)}
                            </select>}
                          </Field>
                          <Field label="Condition">
                            {(p) => <select {...p} className={selectClass} value={rule.op} onChange={(e) => setDraft((current) => current.map((item, i) => i === index ? { ...item, op: e.target.value, value: e.target.value === "none" || e.target.value === "never" ? "" : item.value } : item))}>
                              {field?.ops.map((op) => <option key={op.op} value={op.op}>{op.label}</option>)}
                            </select>}
                          </Field>
                          <Field label="Value">
                            {(p) => {
                              if (noValue) return <div className="flex h-9 items-center text-sm text-muted">No value needed</div>;
                              if (field?.value_kind === "customer_type" || field?.value_kind === "lead_source") {
                                const options = lookups.options(field.value_kind);
                                return <select {...p} className={`${selectClass} h-auto min-h-9`} multiple value={Array.isArray(rule.value) ? rule.value : []} onChange={(e) => updateValue(Array.from(e.target.selectedOptions, (option) => option.value))}>
                                  {options.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                                </select>;
                              }
                              if (field?.value_kind === "tags") return <select {...p} className={`${selectClass} h-auto min-h-9`} multiple value={Array.isArray(rule.value) ? rule.value : []} onChange={(e) => updateValue(Array.from(e.target.selectedOptions, (option) => option.value))}>
                                {tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
                              </select>;
                              if (field?.value_kind === "users") return <select {...p} className={`${selectClass} h-auto min-h-9`} multiple value={Array.isArray(rule.value) ? rule.value : []} onChange={(e) => updateValue(Array.from(e.target.selectedOptions, (option) => option.value))}>
                                {[...directory.people.values()].map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}
                              </select>;
                              if (field?.value_kind === "status") return <select {...p} className={selectClass} value={String(rule.value)} onChange={(e) => updateValue(e.target.value)}>
                                <option value="">Choose a status</option>{STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
                              </select>;
                              if (field?.value_kind === "yesno") return <select {...p} className={selectClass} value={String(rule.value)} onChange={(e) => updateValue(e.target.value)}>
                                <option value="">Choose yes or no</option><option value="true">Yes</option><option value="false">No</option>
                              </select>;
                              return <Input {...p} type="number" min={field?.value_kind === "days" ? 1 : 0} step={field?.value_kind === "money" ? "0.01" : 1} value={String(rule.value)} onChange={(e) => updateValue(e.target.value)} />;
                            }}
                          </Field>
                          <Button type="button" variant="ghost" size="sm" className="text-danger" aria-label={`Remove rule ${index + 1}`} onClick={() => setDraft((current) => current.filter((_, i) => i !== index))} disabled={draft.length === 1}>Remove</Button>
                        </div>
                      );
                    })}
                    <Button type="button" variant="secondary" size="sm" onClick={() => setDraft((current) => [...current, blankRule(fields)])} disabled={draft.length >= 20}>Add rule</Button>
                  </section>
                )}

                <div className="flex flex-wrap gap-2">
                  <Button type="submit" disabled={busy || !form.name.trim() || (form.kind === "segment" && !rulesReady)}>
                    {busy ? "Saving…" : editingId ? "Save segment" : "Create audience"}
                  </Button>
                  {editingId && <Button type="button" variant="secondary" onClick={resetForm}>Cancel</Button>}
                </div>
              </form>
            </PanelBody>
          </Panel>
        )}
      </div>

      {previewId !== null && preview && (
        <Panel className="mt-6">
          <PanelHeader title="Matching customers" description={`${preview.total} customers currently match this segment.`} />
          <PanelBody>
            {preview.items.length ? (
              <ul className="divide-y divide-line">
                {preview.items.map((member) => (
                  <li key={member.customer_id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{member.full_name}{member.company ? ` · ${member.company}` : ""}</div>
                      <div className="truncate text-xs text-muted">{member.email ?? "No email address"}</div>
                    </div>
                    <span className={`text-xs font-medium ${member.reachable ? "text-success" : "text-muted"}`}>
                      {member.reachable ? "Reachable" : "Not reachable"}
                    </span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted">No customers currently match this segment.</p>}
          </PanelBody>
        </Panel>
      )}
    </>
  );
}
