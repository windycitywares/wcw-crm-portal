"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { apiFetch } from "@/lib/client-api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="space-y-3">
        <h1 className="text-xl">Check your email</h1>
        <p className="text-sm text-muted">
          If <strong className="text-ink">{email}</strong> belongs to an active account, we sent a link to choose a new password. It works for 60
          minutes.
        </p>
        <Link href="/login" className="inline-block text-sm text-accent underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      <div>
        <h1 className="text-xl">Reset your password</h1>
        <p className="mt-1 text-sm text-muted">We&apos;ll email you a link to choose a new one.</p>
      </div>
      {error && (
        <p role="alert" className="rounded-[var(--radius-control)] border border-danger/30 bg-danger/8 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      <Field label="Email">
        {(p) => <Input {...p} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />}
      </Field>
      <Button type="submit" className="w-full" disabled={busy || !email}>
        {busy ? "Sending…" : "Email me a link"}
      </Button>
      <p className="text-center text-sm">
        <Link href="/login" className="text-accent underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      </p>
    </form>
  );
}
