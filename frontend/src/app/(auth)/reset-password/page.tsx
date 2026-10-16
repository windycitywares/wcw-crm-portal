"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { useAuth, type TokenResponse } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const { acceptToken } = useAuth();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mismatch = confirm.length > 0 && confirm !== password;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (mismatch) return;
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch<TokenResponse>("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      });
      acceptToken(res);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <div className="space-y-3">
        <h1 className="text-xl">Link incomplete</h1>
        <p className="text-sm text-muted">Open the link from the email again, or ask for a new one.</p>
        <Link href="/forgot-password" className="inline-block text-sm text-accent underline-offset-4 hover:underline">
          Ask for a new link
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      <div>
        <h1 className="text-xl">Choose a new password</h1>
        <p className="mt-1 text-sm text-muted">At least 10 characters. You&apos;ll be signed in straight away.</p>
      </div>
      {error && (
        <p role="alert" className="rounded-[var(--radius-control)] border border-danger/30 bg-danger/8 px-3 py-2 text-sm text-danger">
          {error}{" "}
          <Link href="/forgot-password" className="underline underline-offset-4">
            Ask for a new link
          </Link>
        </p>
      )}
      <Field label="New password">
        {(p) => <Input {...p} type="password" autoComplete="new-password" minLength={10} required value={password} onChange={(e) => setPassword(e.target.value)} />}
      </Field>
      <Field label="Repeat new password" error={mismatch ? "The passwords don't match" : undefined}>
        {(p) => <Input {...p} type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />}
      </Field>
      <Button type="submit" className="w-full" disabled={busy || password.length < 10 || confirm !== password}>
        {busy ? "Saving…" : "Save and sign in"}
      </Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
