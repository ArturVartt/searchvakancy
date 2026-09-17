import { useCallback, useEffect, useState } from "react";
import { JobList } from "../components/JobList";
import { api, ApiError } from "../lib/api";
import type { Job, Paginated } from "../types";

export function FavoritesPage() {
  const [data, setData] = useState<Paginated<Job> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setData(null);
    setError(null);
    api
      .listFavorites()
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Не удалось загрузить избранное"));
  }, []);

  useEffect(load, [load]);

  function handleFavoriteChange(jobId: number, isFavorited: boolean) {
    if (isFavorited) return; // сюда не попадём — тут можно только убирать
    setData((prev) => (prev ? { ...prev, results: prev.results.filter((j) => j.id !== jobId) } : prev));
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Избранные вакансии</h1>
      {error && (
        <p className="mb-3 rounded-lg border border-[var(--color-danger)] px-4 py-2 text-sm text-[var(--color-danger)]">
          {error}
        </p>
      )}
      <JobList
        jobs={data?.results ?? null}
        onFavoriteChange={handleFavoriteChange}
        emptyMessage="Пока ничего не добавлено — нажмите ★ на карточке вакансии."
      />
    </div>
  );
}
