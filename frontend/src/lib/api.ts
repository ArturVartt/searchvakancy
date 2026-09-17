import type {
  Job,
  JobDetail,
  JobFiltersQuery,
  JobNotification,
  JobSource,
  Paginated,
  Stats,
  UserJobFilter,
} from "../types";

// Пусто/не задано -> тот же origin, откуда отдан фронтенд (прод за nginx-прокси,
// см. frontend/nginx.conf). Явный http://localhost:8010 нужен только для
// локальной разработки — его подставляет docker-compose.yml/.env.example.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
const TOKEN_STORAGE_KEY = "searchvakancy.token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token);
    else localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // localStorage недоступен (приватный режим и т.п.) — просто не сохраняем
  }
}

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Token ${token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (response.status === 204) {
    return undefined as T;
  }

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await response.json().catch(() => null) : null;

  if (!response.ok) {
    const message =
      (body && typeof body === "object" && ("detail" in body ? String((body as { detail: unknown }).detail) : JSON.stringify(body))) ||
      response.statusText;
    throw new ApiError(response.status, message, body);
  }

  return body as T;
}

function buildQuery(params: JobFiltersQuery): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      search.set(key, value.join(","));
    } else {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  wsBaseUrl(): string {
    const base = API_BASE_URL || window.location.origin;
    return base.replace(/^http/, "ws");
  },

  // --- публичное -----------------------------------------------------
  listJobs(params: JobFiltersQuery = {}): Promise<Paginated<Job>> {
    return request(`/api/jobs/${buildQuery(params)}`);
  },
  getJob(id: number): Promise<JobDetail> {
    return request(`/api/jobs/${id}/`);
  },
  listSources(): Promise<Paginated<JobSource>> {
    return request(`/api/jobs/sources/`);
  },
  getStats(): Promise<Stats> {
    return request(`/api/jobs/stats/`);
  },

  // --- авторизация -----------------------------------------------------
  login(username: string, password: string): Promise<{ token: string }> {
    return request(`/api/auth/token/`, { method: "POST", body: JSON.stringify({ username, password }) });
  },
  register(username: string, password: string): Promise<{ token: string }> {
    return request(`/api/auth/register/`, { method: "POST", body: JSON.stringify({ username, password }) });
  },

  // --- избранное (нужен токен) ------------------------------------------
  listFavorites(page = 1): Promise<Paginated<Job>> {
    return request(`/api/jobs/favorites/${buildQuery({ page })}`);
  },
  addFavorite(jobId: number): Promise<{ status: string }> {
    return request(`/api/jobs/${jobId}/favorite/`, { method: "POST" });
  },
  removeFavorite(jobId: number): Promise<void> {
    return request(`/api/jobs/${jobId}/favorite/`, { method: "DELETE" });
  },

  // --- фильтры (нужен токен) ---------------------------------------------
  listMyFilters(): Promise<Paginated<UserJobFilter>> {
    return request(`/api/jobs/filters/`);
  },
  createFilter(data: Partial<UserJobFilter>): Promise<UserJobFilter> {
    return request(`/api/jobs/filters/`, { method: "POST", body: JSON.stringify(data) });
  },
  updateFilter(id: number, data: Partial<UserJobFilter>): Promise<UserJobFilter> {
    return request(`/api/jobs/filters/${id}/`, { method: "PATCH", body: JSON.stringify(data) });
  },
  deleteFilter(id: number): Promise<void> {
    return request(`/api/jobs/filters/${id}/`, { method: "DELETE" });
  },

  // --- уведомления (нужен токен) -----------------------------------------
  listNotifications(page = 1): Promise<Paginated<JobNotification>> {
    return request(`/api/jobs/notifications/${buildQuery({ page })}`);
  },
  markNotificationRead(id: number): Promise<JobNotification> {
    return request(`/api/jobs/notifications/${id}/mark_read/`, { method: "POST" });
  },
};
