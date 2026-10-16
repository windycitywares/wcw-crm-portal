"use client";

/** Browser-side API calls. Sends the JWT if signed in; a 401 signs the user out. */

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
const TOKEN_KEY = "wcw-crm-token";

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Listener = () => void;
const signedOutListeners = new Set<Listener>();

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string | null) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* storage unavailable (private mode) */
    }
  },
  /** Called when the API rejects the token (expired, password or role changed). */
  onSignedOut(fn: Listener): () => void {
    signedOutListeners.add(fn);
    return () => {
      signedOutListeners.delete(fn);
    };
  },
};

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) {
      const loc = Array.isArray(detail[0].loc) ? detail[0].loc.slice(1).join(".") : "";
      const msg = String(detail[0].msg).replace(/^Value error, /, "");
      return loc ? `${loc.replace(/_/g, " ")}: ${msg}` : msg;
    }
  }
  return `Request failed (${status})`;
}

export async function apiFetch<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiRequestError(0, "Can't reach the CRM server. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await res.json() : null;
  if (!res.ok) {
    if (res.status === 401 && token) {
      tokenStore.set(null);
      signedOutListeners.forEach((fn) => fn());
    }
    throw new ApiRequestError(res.status, errorMessage(body, res.status));
  }
  return body as T;
}

/** Build a query string, skipping empty values. */
export function qs(params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}
