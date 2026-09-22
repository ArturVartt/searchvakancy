import { useCallback, useEffect, useState } from "react";
import { JobFilters } from "../components/JobFilters";
import { JobList } from "../components/JobList";
import { api, ApiError } from "../lib/api";
import { useJobUpdates } from "../lib/useJobUpdates";
import type { Job, JobFiltersQuery, JobSource, Paginated } from "../types";

const PAGE_SIZE = 20;

export function JobsPage() {
  const [filters, setFilters] = useState<JobFiltersQuery>({});
  const [data, setData] = useState<Paginated<Job> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newCount, setNewCount] = useState(0);
  const [highlightIds, setHighlightIds] = useState<Set<number>>(new Set());
  const [sources, setSources] = useState<JobSource[]>([]);
  // На телефоне форма фильтров разворачивается на весь экран поверх списка
  // вакансий — сворачиваем её по умолчанию за кнопкой-тогглом. На md+
  // (десктоп/планшет) кнопка скрыта (md:hidden), а форма всегда видна
  // (md:block перекрывает hidden независимо от этого стейта).
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    api
      .listSources()
      .then((res) => setSources(res.results))
      .catch(() => setSources([]));
  }, []);

  const load = useCallback((query: JobFiltersQuery) => {
    setData(null);
    setError(null);
    api
      .listJobs(query)
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Не удалось загрузить вакансии"));
  }, []);

  useEffect(() => {
    load(filters);
  }, [filters, load]);

  // Real-time: копим счётчик новых вакансий, не переверстывая список под
  // курсором — пользователь сам решает, когда обновить (баннер сверху).
  useJobUpdates(
    useCallback((event) => {
      if (event.type === "new_job") {
        setNewCount((n) => n + 1);
      }
    }, [])
  );

  function showNewJobs() {
    setNewCount(0);
    api.listJobs({ ...filters, page: 1 }).then((fresh) => {
      setData(fresh);
      const previousIds = new Set((data?.results ?? []).map((j) => j.id));
      setHighlightIds(new Set(fresh.results.filter((j) => !previousIds.has(j.id)).map((j) => j.id)));
      setTimeout(() => setHighlightIds(new Set()), 4000);
    });
  }

  function handleFavoriteChange(jobId: number, isFavorited: boolean) {
    setData((prev) =>
      prev ? { ...prev, results: prev.results.map((j) => (j.id === jobId ? { ...j, is_favorited: isFavorited } : j)) } : prev
    );
  }

  function goToPage(page: number) {
    setFilters((f) => ({ ...f, page }));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const currentPage = filters.page ?? 1;
  const totalPages = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1;
  const activeFilterCount = Object.entries(filters).filter(([key, value]) => {
    if (key === "page") return false;
    if (Array.isArray(value)) return value.length > 0;
    return value !== undefined && value !== "";
  }).length;

  return (
    <div className="grid gap-4 sm:gap-6 md:grid-cols-[280px_1fr]">
      <aside>
        <button
          type="button"
          onClick={() => setFiltersOpen((open) => !open)}
          aria-expanded={filtersOpen}
          className="mb-3 flex w-full items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm font-medium text-[var(--color-text)] md:hidden"
        >
          <span>Фильтры{activeFilterCount > 0 ? ` · ${activeFilterCount}` : ""}</span>
          <span className="text-[var(--color-text-muted)]">{filtersOpen ? "▲" : "▼"}</span>
        </button>
        <div className={`${filtersOpen ? "block" : "hidden"} md:block`}>
          <JobFilters
            value={filters}
            onApply={(next) => {
              setFilters(next);
              setFiltersOpen(false);
            }}
            sources={sources}
          />
        </div>
      </aside>

      <section>
        {newCount > 0 && (
          <button
            type="button"
            onClick={showNewJobs}
            className="mb-3 w-full rounded-lg border border-[var(--color-accent)] bg-[var(--color-surface)] px-4 py-2 text-sm font-medium text-[var(--color-accent)] hover:bg-[var(--color-surface-hover)]"
          >
            ✨ {newCount} {newCount === 1 ? "новая вакансия" : "новых вакансий"} — показать
          </button>
        )}

        {error && (
          <p className="mb-3 rounded-lg border border-[var(--color-danger)] px-4 py-2 text-sm text-[var(--color-danger)]">
            {error}
          </p>
        )}

        <JobList jobs={data?.results ?? null} onFavoriteChange={handleFavoriteChange} highlightIds={highlightIds} />

        {data && totalPages > 1 && (
          <div className="mt-6 flex items-center justify-center gap-2">
            <button
              type="button"
              disabled={currentPage <= 1}
              onClick={() => goToPage(currentPage - 1)}
              className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm disabled:opacity-40"
            >
              ← Назад
            </button>
            <span className="text-sm text-[var(--color-text-muted)]">
              {currentPage} / {totalPages}
            </span>
            <button
              type="button"
              disabled={currentPage >= totalPages}
              onClick={() => goToPage(currentPage + 1)}
              className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Вперёд →
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
