"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { useAuth } from "@/lib/auth";

/** Only same-site paths, so ?next= can't send someone to another website. */
function safeNext(next: string | null) {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

function LoginForm() {
  const { user, login } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace(next);
  }, [user, router, next]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      <div>
        <h1 className="text-xl">Sign in</h1>
        <p className="mt-1 text-sm text-muted">Use your Windy City Wares staff account.</p>
      </div>
      {error && (
        <p role="alert" className="rounded-[var(--radius-control)] border border-danger/30 bg-danger/8 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      <Field label="Email">
        {(p) => <Input {...p} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />}
      </Field>
      <Field label="Password">
        {(p) => <Input {...p} type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />}
      </Field>
      <Button type="submit" className="w-full" disabled={busy || !email || !password}>
        {busy ? "Signing in…" : "Sign in"}
      </Button>
      <p className="text-center text-sm">
        <Link href="/forgot-password" className="text-accent underline-offset-4 hover:underline">
          Forgot your password?
        </Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
