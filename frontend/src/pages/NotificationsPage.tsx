import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { formatDate, formatSalary } from "../lib/format";
import type { JobNotification, Paginated } from "../types";

export function NotificationsPage() {
  const [data, setData] = useState<Paginated<JobNotification> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listNotifications()
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Не удалось загрузить уведомления"));
  }, []);

  async function markRead(id: number) {
    const updated = await api.markNotificationRead(id);
    setData((prev) =>
      prev ? { ...prev, results: prev.results.map((n) => (n.id === id ? updated : n)) } : prev
    );
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Уведомления</h1>
      {error && (
        <p className="mb-3 rounded-lg border border-[var(--color-danger)] px-4 py-2 text-sm text-[var(--color-danger)]">
          {error}
        </p>
      )}

      {data === null && !error && <p className="text-sm text-[var(--color-text-muted)]">Загрузка…</p>}

      {data?.results.length === 0 && (
        <p className="rounded-xl border border-dashed border-[var(--color-border)] p-8 text-center text-[var(--color-text-muted)]">
          Пока пусто — подпишитесь на фильтр в Telegram-боте, чтобы получать вакансии и здесь.
        </p>
      )}

      <ul className="grid gap-2">
        {data?.results.map((n) => (
          <li
            key={n.id}
            className={`flex items-center justify-between gap-3 rounded-xl border p-3 ${
              n.is_read ? "border-[var(--color-border)]" : "border-[var(--color-accent)]"
            } bg-[var(--color-surface)]`}
          >
            <div className="min-w-0">
              <a href={n.job.url} target="_blank" rel="noreferrer" className="truncate font-medium hover:text-[var(--color-accent)]">
                {n.job.title}
              </a>
              <p className="truncate text-xs text-[var(--color-text-muted)]">
                {n.job.company} · {formatSalary(n.job)} · {formatDate(n.notified_at)}
                {n.sent_to_telegram ? " · ✅ отправлено в Telegram" : ""}
              </p>
            </div>
            {!n.is_read && (
              <button
                type="button"
                onClick={() => markRead(n.id)}
                className="shrink-0 rounded-lg border border-[var(--color-border)] px-2.5 py-1 text-xs hover:bg-[var(--color-surface-hover)]"
              >
                Прочитано
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
