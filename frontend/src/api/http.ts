/**
 * Low-level API client: builds the URL from VITE_API_BASE_URL, attaches the
 * in-memory access token, normalizes both the app's own error envelope
 * (`{"error":{"code","message"}}`) and FastAPI's default shapes (`{"detail":
 * "..."}` or Pydantic's `{"detail":[{...}]}`) into one ApiError, and — on a
 * 401 from an authenticated call — attempts exactly one silent refresh
 * (POST /auth/refresh via the httpOnly cookie) before retrying the request
 * once. If that also fails, the caller's session is cleared.
 */
import { getAccessToken, notifyUnauthorized, tryRefresh } from "../lib/authToken";
import { API_BASE_URL } from "../lib/env";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
  headers?: HeadersInit;
  /** Skip the Authorization header + 401-retry dance (login/refresh/logout). */
  anonymous?: boolean;
  query?: Record<string, string | number | undefined | null>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function parseErrorBody(response: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // no JSON body at all
  }

  if (payload && typeof payload === "object") {
    const body = payload as Record<string, unknown>;
    if (body.error && typeof body.error === "object") {
      const err = body.error as Record<string, unknown>;
      return new ApiError(
        response.status,
        String(err.code ?? `HTTP_${response.status}`),
        String(err.message ?? "Request failed"),
      );
    }
    if (typeof body.detail === "string") {
      return new ApiError(response.status, `HTTP_${response.status}`, body.detail);
    }
    if (Array.isArray(body.detail)) {
      const first = body.detail[0] as { msg?: string } | undefined;
      return new ApiError(
        response.status,
        "VALIDATION_ERROR",
        first?.msg ?? "Validation failed",
      );
    }
  }
  return new ApiError(response.status, `HTTP_${response.status}`, response.statusText);
}

async function doFetch(path: string, options: RequestOptions): Promise<Response> {
  const headers = new Headers(options.headers);
  if (!options.formData && options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (!options.anonymous) {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(buildUrl(path, options.query), {
    method: options.method ?? "GET",
    headers,
    credentials: "include",
    body: options.formData ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
  });
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await doFetch(path, options);

  if (response.status === 401 && !options.anonymous) {
    const newToken = await tryRefresh();
    if (newToken) {
      response = await doFetch(path, options);
    } else {
      notifyUnauthorized();
    }
  }

  if (!response.ok) {
    throw await parseErrorBody(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const http = {
  get: <T>(
    path: string,
    query?: RequestOptions["query"],
    options: Omit<RequestOptions, "query"> = {},
  ) => request<T>(path, { ...options, query }),
  post: <T>(path: string, body?: unknown, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: "PATCH", body }),
  postForm: <T>(path: string, formData: FormData, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: "POST", formData }),
  anonymousPost: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body, anonymous: true }),
};

/** {lat,lng,accuracy,timestamp} attached to every geofenced request, read
 * server-side only (Guardrail #5/#6) — the client never decides allow/deny. */
export interface GeoCoords {
  lat: number;
  lng: number;
  accuracy: number;
  timestamp: number;
}

export function geoHeaders(coords: GeoCoords): HeadersInit {
  return {
    "X-Geo-Lat": String(coords.lat),
    "X-Geo-Lng": String(coords.lng),
    "X-Geo-Accuracy": String(coords.accuracy),
    "X-Geo-Timestamp": String(coords.timestamp),
  };
}
