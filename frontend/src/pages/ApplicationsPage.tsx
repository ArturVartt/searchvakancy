import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import {
  APPLICATION_STATUSES,
  APPLICATION_STATUS_CLASSES,
  APPLICATION_STATUS_LABELS,
} from "../lib/applications";
import { formatDate } from "../lib/format";
import type { Application, ApplicationStatus } from "../types";

interface RowProps {
  application: Application;
  onChange: (updated: Application) => void;
  onDelete: (id: number) => void;
  onError: (message: string) => void;
}

function ApplicationRow({ application, onChange, onDelete, onError }: RowProps) {
  const [note, setNote] = useState(application.note);
  const [pending, setPending] = useState(false);
  const { job } = application;

  async function patch(data: { status?: ApplicationStatus; note?: string }) {
    setPending(true);
    try {
      onChange(await api.updateApplication(application.id, data));
    } catch (e) {
      onError(e instanceof ApiError ? e.message : "Не удалось сохранить изменения");
    } finally {
      setPending(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Удалить отклик на «${job.title}»?`)) return;
    setPending(true);
    try {
      await api.deleteApplication(application.id);
      onDelete(application.id);
    } catch (e) {
      onError(e instanceof ApiError ? e.message : "Не удалось удалить отклик");
      setPending(false);
    }
  }

  return (
    <li className="min-w-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 sm:p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <a
            href={job.url}
            target="_blank"
            rel="noreferrer"
            className="block truncate text-sm font-semibold hover:text-[var(--color-accent)] sm:text-base"
          >
            {job.title}
          </a>
          <p className="truncate text-xs text-[var(--color-text-muted)] sm:text-sm">
            {job.company} · {job.source}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-md px-2 py-1 text-xs font-medium ${APPLICATION_STATUS_CLASSES[application.status]}`}
        >
          {APPLICATION_STATUS_LABELS[application.status]}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--color-text-muted)]">
        {application.applied_at && <span>Отклик: {formatDate(application.applied_at)}</span>}
        <span>Сет: {application.profile_set_name ?? "—"}</span>
      </div>

      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-start">
        <select
          value={application.status}
          disabled={pending}
          onChange={(e) => patch({ status: e.target.value as ApplicationStatus })}
          aria-label="Статус отклика"
          className="rounded-lg border border-[var(--color-border)] bg-transparent px-2 py-1.5 text-sm outline-none focus:border-[var(--color-accent)] sm:w-44"
        >
          {APPLICATION_STATUSES.map((s) => (
            <option key={s} value={s}>
              {APPLICATION_STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <textarea
          rows={2}
          value={note}
          disabled={pending}
          onChange={(e) => setNote(e.target.value)}
          onBlur={() => {
            if (note !== application.note) patch({ note });
          }}
          placeholder="Заметка…"
          className="min-w-0 flex-1 rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--color-accent)]"
        />
        <button
          type="button"
          onClick={handleDelete}
          disabled={pending}
          className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm text-[var(--color-danger)] hover:bg-[var(--color-surface-hover)] disabled:opacity-50"
        >
          Удалить
        </button>
      </div>
    </li>
  );
}

export function ApplicationsPage() {
  const [items, setItems] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ApplicationStatus | "all">("all");

  useEffect(() => {
    api
      .listApplications()
      .then(setItems)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Не удалось загрузить отклики"));
  }, []);

  const counts = new Map<ApplicationStatus, number>();
  for (const a of items ?? []) counts.set(a.status, (counts.get(a.status) ?? 0) + 1);
  const visible = (items ?? []).filter((a) => filter === "all" || a.status === filter);

  const chipClass = (active: boolean) =>
    `shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium ${
      active
        ? "bg-[var(--color-accent)] text-[var(--color-accent-contrast)]"
        : "bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]"
    }`;

  return (
    <div className="min-w-0">
      <h1 className="mb-4 text-xl font-semibold">Мои отклики</h1>

      {error && (
        <p className="mb-3 rounded-lg border border-[var(--color-danger)] px-4 py-2 text-sm text-[var(--color-danger)]">
          {error}
        </p>
      )}

      <div className="mb-4 flex gap-1.5 overflow-x-auto pb-1 scrollbar-none">
        <button type="button" onClick={() => setFilter("all")} className={chipClass(filter === "all")}>
          Все · {items?.length ?? 0}
        </button>
        {APPLICATION_STATUSES.map((s) => (
          <button key={s} type="button" onClick={() => setFilter(s)} className={chipClass(filter === s)}>
            {APPLICATION_STATUS_LABELS[s]} · {counts.get(s) ?? 0}
          </button>
        ))}
      </div>

      {items === null && !error ? (
        <p className="text-sm text-[var(--color-text-muted)]">Загрузка…</p>
      ) : visible.length === 0 ? (
        <p className="rounded-xl border border-dashed border-[var(--color-border)] px-4 py-6 text-center text-sm text-[var(--color-text-muted)]">
          {items && items.length > 0 ? (
            "Нет откликов с таким статусом."
          ) : (
            <>
              Пока нет откликов — нажмите «Откликнуться» на карточке вакансии в{" "}
              <Link to="/" className="text-[var(--color-accent)]">
                списке
              </Link>
              .
            </>
          )}
        </p>
      ) : (
        <ul className="grid grid-cols-1 gap-2">
          {visible.map((a) => (
            <ApplicationRow
              key={a.id}
              application={a}
              onChange={(updated) => setItems((prev) => prev?.map((x) => (x.id === updated.id ? updated : x)) ?? prev)}
              onDelete={(id) => setItems((prev) => prev?.filter((x) => x.id !== id) ?? prev)}
              onError={setError}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
