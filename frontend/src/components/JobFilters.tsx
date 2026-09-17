import { useState, type FormEvent } from "react";
import type { EmploymentType, ExperienceLevel, JobFiltersQuery, JobType } from "../types";
import { EMPLOYMENT_LABELS, EXPERIENCE_LABELS } from "../lib/format";

const JOB_TYPE_LABELS: Record<JobType, string> = {
  full_time: "Постоянная",
  contract: "Контракт",
  freelance: "Фриланс",
  internship: "Стажировка",
};

const EXPERIENCE_OPTIONS = Object.keys(EXPERIENCE_LABELS) as ExperienceLevel[];
const EMPLOYMENT_OPTIONS = Object.keys(EMPLOYMENT_LABELS) as EmploymentType[];
const JOB_TYPE_OPTIONS = Object.keys(JOB_TYPE_LABELS) as JobType[];

interface JobFiltersProps {
  value: JobFiltersQuery;
  onApply: (next: JobFiltersQuery) => void;
}

function toggle<T>(list: T[] | undefined, item: T): T[] {
  const current = list ?? [];
  return current.includes(item) ? current.filter((x) => x !== item) : [...current, item];
}

export function JobFilters({ value, onApply }: JobFiltersProps) {
  const [draft, setDraft] = useState<JobFiltersQuery>(value);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onApply({ ...draft, page: 1 });
  }

  function handleReset() {
    const empty: JobFiltersQuery = {};
    setDraft(empty);
    onApply(empty);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Ключевые слова</label>
        <input
          type="text"
          value={draft.search ?? ""}
          onChange={(e) => setDraft({ ...draft, search: e.target.value })}
          placeholder="react, vue…"
          className="w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--color-accent)]"
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Зарплата от</label>
          <input
            type="number"
            min={0}
            value={draft.min_salary ?? ""}
            onChange={(e) => setDraft({ ...draft, min_salary: e.target.value ? Number(e.target.value) : undefined })}
            className="w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--color-accent)]"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Зарплата до</label>
          <input
            type="number"
            min={0}
            value={draft.max_salary ?? ""}
            onChange={(e) => setDraft({ ...draft, max_salary: e.target.value ? Number(e.target.value) : undefined })}
            className="w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--color-accent)]"
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Город / "Удалённо"</label>
        <input
          type="text"
          value={draft.location ?? ""}
          onChange={(e) => setDraft({ ...draft, location: e.target.value })}
          placeholder="Москва…"
          className="w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--color-accent)]"
        />
      </div>

      <fieldset>
        <legend className="mb-1 text-xs font-medium text-[var(--color-text-muted)]">Опыт</legend>
        <div className="flex flex-wrap gap-2">
          {EXPERIENCE_OPTIONS.map((level) => (
            <label
              key={level}
              className="flex cursor-pointer items-center gap-1.5 rounded-full border border-[var(--color-border)] px-2.5 py-1 text-xs has-checked:border-[var(--color-accent)] has-checked:text-[var(--color-accent)]"
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={draft.experience_level?.includes(level) ?? false}
                onChange={() => setDraft({ ...draft, experience_level: toggle(draft.experience_level, level) })}
              />
              {EXPERIENCE_LABELS[level]}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-1 text-xs font-medium text-[var(--color-text-muted)]">Тип занятости</legend>
        <div className="flex flex-wrap gap-2">
          {JOB_TYPE_OPTIONS.map((type) => (
            <label
              key={type}
              className="flex cursor-pointer items-center gap-1.5 rounded-full border border-[var(--color-border)] px-2.5 py-1 text-xs has-checked:border-[var(--color-accent)] has-checked:text-[var(--color-accent)]"
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={draft.job_type?.includes(type) ?? false}
                onChange={() => setDraft({ ...draft, job_type: toggle(draft.job_type, type) })}
              />
              {JOB_TYPE_LABELS[type]}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-1 text-xs font-medium text-[var(--color-text-muted)]">График</legend>
        <div className="flex flex-wrap gap-2">
          {EMPLOYMENT_OPTIONS.map((type) => (
            <label
              key={type}
              className="flex cursor-pointer items-center gap-1.5 rounded-full border border-[var(--color-border)] px-2.5 py-1 text-xs has-checked:border-[var(--color-accent)] has-checked:text-[var(--color-accent)]"
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={draft.employment_type?.includes(type) ?? false}
                onChange={() => setDraft({ ...draft, employment_type: toggle(draft.employment_type, type) })}
              />
              {EMPLOYMENT_LABELS[type]}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="flex gap-2">
        <button
          type="submit"
          className="flex-1 rounded-lg bg-[var(--color-accent)] px-3 py-2 text-sm font-medium text-[var(--color-accent-contrast)] hover:bg-[var(--color-accent-hover)]"
        >
          Применить
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
        >
          Сбросить
        </button>
      </div>
    </form>
  );
}
