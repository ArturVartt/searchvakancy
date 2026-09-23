import { useState } from "react";
import type { Job } from "../types";
import { EMPLOYMENT_LABELS, EXPERIENCE_LABELS, formatDate, formatSalary } from "../lib/format";
import { useAuth } from "../lib/AuthContext";
import { api } from "../lib/api";
import { isJobViewed, isPostedWithinLastDay, markJobViewed } from "../lib/viewedJobs";
import { sourceBadge } from "../lib/countryBadge";
import { isTelegramSource } from "../lib/telegramSource";
import { TelegramIcon } from "./TelegramIcon";

interface JobCardProps {
  job: Job;
  onFavoriteChange?: (jobId: number, isFavorited: boolean) => void;
  highlight?: boolean;
}

export function JobCard({ job, onFavoriteChange, highlight }: JobCardProps) {
  const { isAuthenticated } = useAuth();
  const [pending, setPending] = useState(false);
  const [viewed, setViewed] = useState(() => isJobViewed(job.id));
  const isUnseenAndNew = !viewed && isPostedWithinLastDay(job.posted_at);
  const badge = sourceBadge(job.source);
  const isTG = isTelegramSource(job.source);

  function handleOpen() {
    markJobViewed(job.id);
    setViewed(true);
  }

  async function toggleFavorite() {
    if (!isAuthenticated || pending) return;
    setPending(true);
    try {
      if (job.is_favorited) {
        await api.removeFavorite(job.id);
        onFavoriteChange?.(job.id, false);
      } else {
        await api.addFavorite(job.id);
        onFavoriteChange?.(job.id, true);
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <article
      className={`rounded-md border p-2 transition-colors sm:rounded-xl sm:p-4 ${
        isTG
          ? "border-blue-400 dark:border-blue-500"
          : highlight
            ? "border-[var(--color-accent)]"
            : "border-[var(--color-border)]"
      } ${isUnseenAndNew ? "ring-2 ring-yellow-400" : ""} bg-[var(--color-surface)]`}
    >
      <div className="flex items-start justify-between gap-1.5 sm:gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-xs font-semibold leading-snug text-[var(--color-text)] sm:text-base">
            {job.title}
          </h3>
          <p className="truncate text-[10px] text-[var(--color-text-muted)] sm:text-sm">{job.company}</p>
        </div>
        {isAuthenticated && (
          <button
            type="button"
            onClick={toggleFavorite}
            disabled={pending}
            aria-label={job.is_favorited ? "Убрать из избранного" : "Добавить в избранное"}
            aria-pressed={job.is_favorited}
            className="shrink-0 text-sm leading-none disabled:opacity-50 sm:text-xl"
          >
            <span className={job.is_favorited ? "text-yellow-400" : "text-[var(--color-text-muted)]"}>
              {job.is_favorited ? "★" : "☆"}
            </span>
          </button>
        )}
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[10px] text-[var(--color-text-muted)] sm:mt-3 sm:gap-x-3 sm:gap-y-1 sm:text-sm">
        <span className="font-medium text-[var(--color-text)]">{formatSalary(job)}</span>
        {job.location && <span>📍 {job.location}</span>}
        {job.experience_level && <span>{EXPERIENCE_LABELS[job.experience_level]}</span>}
        {job.employment_type && <span className="hidden sm:inline">{EMPLOYMENT_LABELS[job.employment_type]}</span>}
      </div>

      {job.required_skills.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1 sm:mt-3 sm:gap-1.5">
          {job.required_skills.slice(0, 3).map((skill) => (
            <span
              key={skill}
              className="rounded-full bg-[var(--color-surface-hover)] px-1.5 py-0.5 text-[9px] text-[var(--color-text-muted)] sm:text-xs"
            >
              {skill}
            </span>
          ))}
          {/* Остальные скилы — только на sm+, на телефоне вместо них счётчик
              "+N", чтобы карточка не растягивалась в высоту тегами. */}
          {job.required_skills.slice(3).map((skill) => (
            <span
              key={skill}
              className="hidden rounded-full bg-[var(--color-surface-hover)] px-2 py-0.5 text-xs text-[var(--color-text-muted)] sm:inline-block"
            >
              {skill}
            </span>
          ))}
          {job.required_skills.length > 3 && (
            <span className="rounded-full bg-[var(--color-surface-hover)] px-1.5 py-0.5 text-[9px] text-[var(--color-text-muted)] sm:hidden">
              +{job.required_skills.length - 3}
            </span>
          )}
        </div>
      )}

      <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-[var(--color-text-muted)] sm:mt-3 sm:text-xs">
        <span className="inline-flex min-w-0 items-center gap-1 truncate sm:gap-1.5">
          {isTG && (
            <span className="inline-flex shrink-0 items-center gap-0.5 rounded bg-blue-100 px-1 py-0.5 font-semibold text-blue-600 dark:bg-blue-950 dark:text-blue-300">
              <TelegramIcon className="h-2.5 w-2.5" />
              TG
            </span>
          )}
          {badge && (
            <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold ${badge.className}`}>
              {badge.label}
            </span>
          )}
          <span className="truncate">
            {job.source}
            {job.posted_at ? ` · ${formatDate(job.posted_at)}` : ""}
          </span>
        </span>
        <a
          href={job.url}
          target="_blank"
          rel="noreferrer"
          onClick={handleOpen}
          className="shrink-0 font-medium text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
        >
          Открыть →
        </a>
      </div>
    </article>
  );
}
