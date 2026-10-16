"use client";

import { useEffect, useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ColorTag } from "@/components/ui/ColorTag";
import { Input } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { tagsApi, type Tag } from "@/modules/settings/api";
import { recordsApi, type RecordRef } from "./api";

/** A record's tags with inline editing: type to pick an existing tag or create a new one. */
export function TagEditor({ record, canEdit, onChange }: { record: RecordRef; canEdit: boolean; onChange?: () => void }) {
  const toast = useToast();
  const listId = useId();
  const [tags, setTags] = useState<Tag[] | null>(null);
  const [editing, setEditing] = useState(false);
  const [names, setNames] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<Tag[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    recordsApi
      .tags(record)
      .then(setTags)
      .catch(() => setTags([]));
  }, [record.type, record.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!editing) return;
    const t = window.setTimeout(() => {
      tagsApi
        .search(input, 20)
        .then(setSuggestions)
        .catch(() => setSuggestions([]));
    }, 200);
    return () => window.clearTimeout(t);
  }, [editing, input]);

  function addName(raw: string) {
    const name = raw.trim().replace(/\s+/g, " ");
    if (name && !names.some((n) => n.toLowerCase() === name.toLowerCase())) setNames([...names, name]);
    setInput("");
  }

  async function save() {
    setBusy(true);
    try {
      const all = input.trim() ? [...names, input.trim()] : names;
      setTags(await recordsApi.setTags(record, all));
      setEditing(false);
      setInput("");
      toast.push({ title: "Tags saved" });
      onChange?.();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't save tags", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  if (!editing) {
    return (
      <div className="flex flex-wrap items-center gap-1.5">
        {tags?.map((t) => (
          <ColorTag key={t.id} color={t.color}>
            {t.name}
          </ColorTag>
        ))}
        {tags?.length === 0 && <span className="text-sm text-muted">No tags</span>}
        {canEdit && (
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={() => {
              setNames((tags ?? []).map((t) => t.name));
              setEditing(true);
            }}
          >
            <Icon name="tag" className="size-3.5" />
            Edit tags
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="grid gap-2">
      <ul className="flex flex-wrap gap-1.5" aria-label="Tags to save">
        {names.map((n) => (
          <li key={n} className="inline-flex items-center gap-1 rounded-full bg-sand py-0.5 pl-2.5 pr-1 text-xs font-medium">
            {n}
            <button type="button" onClick={() => setNames(names.filter((x) => x !== n))} className="grid size-5 place-items-center rounded-full hover:bg-line">
              <Icon name="close" className="size-3" />
              <span className="sr-only">Remove {n}</span>
            </button>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={`${listId}-input`} className="sr-only">
          Add a tag
        </label>
        <Input
          id={`${listId}-input`}
          list={listId}
          className="max-w-xs py-1.5"
          placeholder="Type a tag and press Enter"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              addName(input);
            }
          }}
        />
        <datalist id={listId}>
          {suggestions.map((s) => (
            <option key={s.id} value={s.name} />
          ))}
        </datalist>
        <Button size="sm" onClick={() => void save()} disabled={busy}>
          {busy ? "Saving…" : "Save tags"}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
