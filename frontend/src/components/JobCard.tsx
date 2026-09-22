import { useState } from "react";
import type { Job } from "../types";
import { EMPLOYMENT_LABELS, EXPERIENCE_LABELS, formatDate, formatSalary } from "../lib/format";
import { useAuth } from "../lib/AuthContext";
import { api } from "../lib/api";
import { isJobViewed, isPostedWithinLastDay, markJobViewed } from "../lib/viewedJobs";

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
      className={`rounded-xl border p-4 transition-colors ${
        highlight ? "border-[var(--color-accent)]" : "border-[var(--color-border)]"
      } ${isUnseenAndNew ? "ring-2 ring-yellow-400" : ""} bg-[var(--color-surface)]`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-[var(--color-text)]">{job.title}</h3>
          <p className="truncate text-sm text-[var(--color-text-muted)]">{job.company}</p>
        </div>
        {isAuthenticated && (
          <button
            type="button"
            onClick={toggleFavorite}
            disabled={pending}
            aria-label={job.is_favorited ? "Убрать из избранного" : "Добавить в избранное"}
            aria-pressed={job.is_favorited}
            className="shrink-0 text-xl leading-none disabled:opacity-50"
          >
            <span className={job.is_favorited ? "text-yellow-400" : "text-[var(--color-text-muted)]"}>
              {job.is_favorited ? "★" : "☆"}
            </span>
          </button>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-[var(--color-text-muted)]">
        <span className="font-medium text-[var(--color-text)]">{formatSalary(job)}</span>
        {job.location && <span>📍 {job.location}</span>}
        {job.experience_level && <span>{EXPERIENCE_LABELS[job.experience_level]}</span>}
        {job.employment_type && <span>{EMPLOYMENT_LABELS[job.employment_type]}</span>}
      </div>

      {job.required_skills.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {job.required_skills.map((skill) => (
            <span
              key={skill}
              className="rounded-full bg-[var(--color-surface-hover)] px-2 py-0.5 text-xs text-[var(--color-text-muted)]"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between text-xs text-[var(--color-text-muted)]">
        <span>{job.source}{job.posted_at ? ` · ${formatDate(job.posted_at)}` : ""}</span>
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
