const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const REFRESH_KEY = "rm_refresh";

export type Role = "admin" | "recruiter" | "candidate";
export type Me = { id: string; email: string; role: Role; org_id: string };
type Tokens = { access_token: string; refresh_token: string | null; token_type: string };

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let accessToken: string | null = null;
let onSessionExpired: (() => void) | null = null;
let refreshing: Promise<boolean> | null = null;

function readRefresh(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

function writeRefresh(token: string | null): void {
  try {
    if (token) localStorage.setItem(REFRESH_KEY, token);
    else localStorage.removeItem(REFRESH_KEY);
  } catch {
    // storage unavailable: the session just will not survive a reload
  }
}

function saveTokens(t: Tokens): void {
  accessToken = t.access_token;
  writeRefresh(t.refresh_token);
}

function clearTokens(): void {
  accessToken = null;
  writeRefresh(null);
}

export function setSessionExpiredHandler(fn: (() => void) | null): void {
  onSessionExpired = fn;
}

export function hasStoredSession(): boolean {
  return readRefresh() !== null;
}

function messageFrom(data: unknown, status: number): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
        .filter(Boolean);
      if (msgs.length) return msgs.join("; ");
    }
  }
  return `Request failed (${status})`;
}

// One refresh at a time. The backend revokes the whole session if a used
// refresh token is presented again, so parallel refreshes must share one call.
export function restoreSession(): Promise<boolean> {
  const token = readRefresh();
  if (!token) return Promise.resolve(false);
  if (!refreshing) {
    refreshing = (async () => {
      try {
        let res: Response;
        try {
          res = await fetch(`${API_URL}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: token }),
          });
        } catch {
          throw new ApiError(0, "Cannot reach the server. Check your connection.");
        }
        if (res.ok) {
          saveTokens((await res.json()) as Tokens);
          return true;
        }
        if (res.status === 401) return false; // expired or revoked: a real sign-out
        throw new ApiError(res.status, "Could not refresh the session");
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

type Options = { method?: string; json?: unknown; form?: FormData; auth?: boolean };

export async function request<T>(path: string, opts: Options = {}): Promise<T> {
  const { method = "GET", json, form, auth = true } = opts;

  const send = async (): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`;
    let body: BodyInit | undefined;
    if (json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(json);
    } else if (form) {
      body = form;
    }
    try {
      return await fetch(`${API_URL}${path}`, { method, headers, body });
    } catch {
      throw new ApiError(0, "Cannot reach the server. Check your connection.");
    }
  };

  let res = await send();
  if (res.status === 401 && auth) {
    if (await restoreSession()) {
      res = await send();
    } else {
      clearTokens();
      onSessionExpired?.();
    }
  }
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, messageFrom(data, res.status));
  return data as T;
}

export async function login(email: string, password: string): Promise<void> {
  saveTokens(await request<Tokens>("/auth/login", { method: "POST", json: { email, password }, auth: false }));
}

export async function registerOrg(orgName: string, email: string, password: string): Promise<void> {
  saveTokens(
    await request<Tokens>("/auth/register-org", {
      method: "POST",
      json: { org_name: orgName, email, password },
      auth: false,
    }),
  );
}

export async function registerCandidate(orgId: string, email: string, password: string): Promise<void> {
  saveTokens(
    await request<Tokens>("/auth/register-candidate", {
      method: "POST",
      json: { org_id: orgId, email, password },
      auth: false,
    }),
  );
}

export async function logout(): Promise<void> {
  const token = readRefresh();
  clearTokens();
  if (token) {
    try {
      await request("/auth/logout", { method: "POST", json: { refresh_token: token }, auth: false });
    } catch {
      // already signed out locally: nothing more to do
    }
  }
}

export const getMe = () => request<Me>("/auth/me");
