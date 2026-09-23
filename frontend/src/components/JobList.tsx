import type { Job } from "../types";
import { JobCard } from "./JobCard";

interface JobListProps {
  jobs: Job[] | null;
  onFavoriteChange?: (jobId: number, isFavorited: boolean) => void;
  highlightIds?: Set<number>;
  emptyMessage?: string;
}

function JobCardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="h-4 w-2/3 rounded bg-[var(--color-surface-hover)]" />
      <div className="mt-2 h-3 w-1/3 rounded bg-[var(--color-surface-hover)]" />
      <div className="mt-4 h-3 w-1/2 rounded bg-[var(--color-surface-hover)]" />
    </div>
  );
}

export function JobList({ jobs, onFavoriteChange, highlightIds, emptyMessage }: JobListProps) {
  if (jobs === null) {
    return (
      <div className="grid grid-cols-1 gap-2 sm:gap-3">
        {Array.from({ length: 6 }, (_, i) => (
          <JobCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-[var(--color-border)] p-8 text-center text-[var(--color-text-muted)]">
        {emptyMessage ?? "Ничего не найдено — попробуйте изменить фильтры."}
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-2 sm:gap-3">
      {jobs.map((job) => (
        <JobCard
          key={job.id}
          job={job}
          onFavoriteChange={onFavoriteChange}
          highlight={highlightIds?.has(job.id)}
        />
      ))}
    </div>
  );
}
