"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiFetch, tokenStore } from "./client-api";
import type { Me } from "./types";

interface TokenResponse {
  access_token: string;
  user: Me;
}

interface AuthState {
  user: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  /** Store a token returned by reset-password / change-password and the user that came with it. */
  acceptToken: (res: TokenResponse) => void;
  logout: () => void;
  refresh: () => Promise<void>;
  setUser: (user: Me) => void;
  /** UI hint only: the API checks every permission again. */
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!tokenStore.get()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await apiFetch<Me>("/auth/me"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    return tokenStore.onSignedOut(() => setUser(null));
  }, [refresh]);

  const acceptToken = useCallback((res: TokenResponse) => {
    tokenStore.set(res.access_token);
    setUser(res.user);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await apiFetch<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      acceptToken(res);
      return res.user;
    },
    [acceptToken],
  );

  const logout = useCallback(() => {
    tokenStore.set(null);
    setUser(null);
  }, []);

  const can = useCallback((permission: string) => !!user?.permissions.includes(permission), [user]);

  const value = useMemo<AuthState>(
    () => ({ user, loading, login, acceptToken, logout, refresh, setUser, can }),
    [user, loading, login, acceptToken, logout, refresh, can],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export type { TokenResponse };
