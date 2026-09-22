import { useState } from "react";
import type { Job } from "../types";
import { EMPLOYMENT_LABELS, EXPERIENCE_LABELS, formatDate, formatSalary } from "../lib/format";
import { useAuth } from "../lib/AuthContext";
import { api } from "../lib/api";
import { isJobViewed, isPostedWithinLastDay, markJobViewed } from "../lib/viewedJobs";
import { sourceBadge } from "../lib/countryBadge";

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
      className={`rounded-lg border p-3 transition-colors sm:rounded-xl sm:p-4 ${
        highlight ? "border-[var(--color-accent)]" : "border-[var(--color-border)]"
      } ${isUnseenAndNew ? "ring-2 ring-yellow-400" : ""} bg-[var(--color-surface)]`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-[var(--color-text)] sm:text-base">{job.title}</h3>
          <p className="truncate text-xs text-[var(--color-text-muted)] sm:text-sm">{job.company}</p>
        </div>
        {isAuthenticated && (
          <button
            type="button"
            onClick={toggleFavorite}
            disabled={pending}
            aria-label={job.is_favorited ? "Убрать из избранного" : "Добавить в избранное"}
            aria-pressed={job.is_favorited}
            className="shrink-0 text-lg leading-none disabled:opacity-50 sm:text-xl"
          >
            <span className={job.is_favorited ? "text-yellow-400" : "text-[var(--color-text-muted)]"}>
              {job.is_favorited ? "★" : "☆"}
            </span>
          </button>
        )}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[var(--color-text-muted)] sm:mt-3 sm:gap-x-3 sm:text-sm">
        <span className="font-medium text-[var(--color-text)]">{formatSalary(job)}</span>
        {job.location && <span>📍 {job.location}</span>}
        {job.experience_level && <span>{EXPERIENCE_LABELS[job.experience_level]}</span>}
        {job.employment_type && <span>{EMPLOYMENT_LABELS[job.employment_type]}</span>}
      </div>

      {job.required_skills.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1 sm:mt-3 sm:gap-1.5">
          {job.required_skills.map((skill) => (
            <span
              key={skill}
              className="rounded-full bg-[var(--color-surface-hover)] px-1.5 py-0.5 text-[11px] text-[var(--color-text-muted)] sm:px-2 sm:text-xs"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      <div className="mt-2 flex items-center justify-between text-xs text-[var(--color-text-muted)] sm:mt-3">
        <span className="inline-flex items-center gap-1.5">
          {badge && (
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${badge.className}`}>
              {badge.label}
            </span>
          )}
          {job.source}
          {job.posted_at ? ` · ${formatDate(job.posted_at)}` : ""}
        </span>
        <a
          href={job.url}
          target="_blank"
          rel="noreferrer"
          onClick={handleOpen}
          className="font-medium text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
        >
          Открыть →
        </a>
      </div>
    </article>
  );
}
