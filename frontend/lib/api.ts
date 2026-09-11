import type { HealthResponse, RefreshResponse, SearchResponse } from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
  } catch {
    throw new ApiError(
      "Could not reach the backend. Is it running on " + BASE + " ?",
      0,
    );
  }
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail =
      (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    throw new ApiError(typeof detail === "string" ? detail : "Request failed", res.status);
  }
  return data as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function searchCreators(
  brief: string,
  limit = 8,
  forceRefresh = false,
): Promise<SearchResponse> {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify({ brief, limit, force_refresh: forceRefresh }),
  });
}

export function refreshCreator(id: number): Promise<RefreshResponse> {
  return request<RefreshResponse>(`/api/creators/${id}/refresh`, { method: "POST" });
}
