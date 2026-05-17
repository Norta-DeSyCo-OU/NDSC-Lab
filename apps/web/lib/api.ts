const PUBLIC_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
// Server-side (SSR / Server Components) cannot use the relative "/api" path because
// it has no concept of a browser origin. Use the in-cluster API URL there.
const SERVER_API_BASE = process.env.INTERNAL_API_BASE_URL ?? "http://api:8000";

export function apiUrl(path: string): string {
  const base = typeof window === "undefined" ? SERVER_API_BASE : PUBLIC_API_BASE;
  return `${base}${path}`;
}

function readCsrfCookie(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

/**
 * Reads the CURRENT CSRF cookie before every state-changing request.
 *
 * Important: do NOT cache the token across calls. The server rotates the
 * `ndsc_csrf` cookie on every state-changing response (login, signup, etc.),
 * so a cached value diverges from what the browser actually sends as the
 * cookie on the next request, producing `csrf_failed`. The browser jar is
 * the source of truth.
 */
async function ensureCsrf(): Promise<string> {
  let tok = readCsrfCookie();
  if (tok) return tok;
  // No cookie yet — bootstrap by calling /csrf.
  let r: Response;
  try {
    r = await fetch(apiUrl("/csrf"), { credentials: "include" });
  } catch (e) {
    throw new ApiError(0, "csrf_network_error", { cause: String(e) });
  }
  if (!r.ok) throw new ApiError(r.status, "csrf_fetch_failed");
  tok = readCsrfCookie();
  if (!tok) {
    throw new ApiError(
      0,
      "csrf_cookie_blocked",
      "Browser blocked the CSRF cookie. Check that cookies are enabled for this site (private browsing or strict tracking-prevention can block them).",
    );
  }
  return tok;
}

function extractDetail(data: Record<string, unknown>): string {
  const d = data["detail"];
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length > 0) {
    const first = d[0] as { msg?: string; loc?: unknown[] };
    const msg = first?.msg ?? "validation_error";
    const loc = Array.isArray(first?.loc) ? first.loc.slice(-1)[0] : "";
    return loc ? `${msg} (${loc})` : msg;
  }
  if (d && typeof d === "object") {
    try {
      return JSON.stringify(d);
    } catch {
      /* fallthrough */
    }
  }
  return "request_failed";
}

async function sendJson<T>(method: string, path: string, body?: unknown): Promise<T> {
  const tok = await ensureCsrf();
  let r: Response;
  try {
    r = await fetch(apiUrl(path), {
      method,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": tok,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(0, "network_error", { cause: String(e) });
  }
  const data = (await r.json().catch(() => ({}))) as Record<string, unknown>;
  if (r.status === 403) {
    // CSRF mismatch can happen if the server rotated the cookie between our
    // read and our send (rare race). One retry with the freshly-read cookie.
    const detail = extractDetail(data);
    if (detail === "csrf_failed") {
      const retryTok = readCsrfCookie();
      if (retryTok && retryTok !== tok) {
        try {
          r = await fetch(apiUrl(path), {
            method,
            credentials: "include",
            headers: {
              "Content-Type": "application/json",
              "X-CSRF-Token": retryTok,
            },
            body: body !== undefined ? JSON.stringify(body) : undefined,
          });
        } catch (e) {
          throw new ApiError(0, "network_error", { cause: String(e) });
        }
        const retryData = (await r.json().catch(() => ({}))) as Record<string, unknown>;
        if (!r.ok) throw new ApiError(r.status, extractDetail(retryData), retryData);
        return retryData as T;
      }
    }
    throw new ApiError(r.status, detail, data);
  }
  if (!r.ok) throw new ApiError(r.status, extractDetail(data), data);
  return data as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>("POST", path, body);
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>("PUT", path, body);
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>("PATCH", path, body);
}

export async function apiDelete<T>(path: string): Promise<T> {
  return sendJson<T>("DELETE", path);
}

export async function apiGet<T>(path: string): Promise<T> {
  let r: Response;
  try {
    r = await fetch(apiUrl(path), { credentials: "include" });
  } catch (e) {
    throw new ApiError(0, "network_error", { cause: String(e) });
  }
  const data = (await r.json().catch(() => ({}))) as Record<string, unknown>;
  if (!r.ok) throw new ApiError(r.status, extractDetail(data), data);
  return data as T;
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, public payload?: unknown) {
    super(code);
  }
}
