import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import type { ProfileSet } from "../types";

function resumeFileName(url: string): string {
  try {
    return decodeURIComponent(url.split("/").pop() ?? "резюме");
  } catch {
    return "резюме";
  }
}

export function ProfileSetsPage() {
  const [sets, setSets] = useState<ProfileSet[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = useCallback(() => {
    setError(null);
    api
      .listProfileSets()
      .then((res) => setSets(res.results))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Не удалось загрузить сеты профиля"));
  }, []);

  useEffect(load, [load]);

  async function handleDelete(id: number) {
    if (!window.confirm("Удалить этот сет профиля? Это действие необратимо.")) return;
    setDeletingId(id);
    try {
      await api.deleteProfileSet(id);
      setSets((prev) => prev?.filter((s) => s.id !== id) ?? prev);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не удалось удалить сет профиля");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold">Сеты профиля</h1>
      <p className="mb-4 text-sm text-[var(--color-text-muted)]">
        Разные наборы контактов и резюме для отклика на вакансии — удобно, если резюме несколько.
      </p>

      {error && (
        <p className="mb-3 rounded-lg border border-[var(--color-danger)] px-4 py-2 text-sm text-[var(--color-danger)]">
          {error}
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {sets?.map((set) => (
          <article
            key={set.id}
            className="flex flex-col gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
          >
            <h3 className="truncate text-base font-semibold text-[var(--color-text)]">{set.name}</h3>

            <div className="flex flex-col gap-1 text-sm text-[var(--color-text-muted)]">
              {set.phone && <span>📱 {set.phone}</span>}
              {set.email && <span className="truncate">✉️ {set.email}</span>}
              {set.github_url && (
                <a
                  href={set.github_url}
                  target="_blank"
                  rel="noreferrer"
                  className="truncate text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
                >
                  🔗 {set.github_url.replace(/^https?:\/\//, "")}
                </a>
              )}
              <a
                href={set.resume}
                target="_blank"
                rel="noreferrer"
                className="truncate text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
              >
                📄 {resumeFileName(set.resume)}
              </a>
            </div>

            <div className="mt-2 flex gap-2 text-sm">
              <Link
                to={`/profile-sets/${set.id}/edit`}
                className="flex-1 rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-center hover:bg-[var(--color-surface-hover)]"
              >
                Изменить
              </Link>
              <button
                type="button"
                onClick={() => handleDelete(set.id)}
                disabled={deletingId === set.id}
                className="rounded-lg border border-[var(--color-danger)] px-3 py-1.5 text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 disabled:opacity-50"
              >
                {deletingId === set.id ? "…" : "Удалить"}
              </button>
            </div>
          </article>
        ))}

        <Link
          to="/profile-sets/new"
          className="flex min-h-[140px] flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-[var(--color-border)] p-4 text-[var(--color-text-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
        >
          <span className="text-2xl leading-none">+</span>
          <span className="text-sm font-medium">Добавить сет</span>
        </Link>
      </div>

      {sets === null && !error && <p className="text-sm text-[var(--color-text-muted)]">Загрузка…</p>}
    </div>
  );
}
