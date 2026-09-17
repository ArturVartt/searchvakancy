import type { EmploymentType, ExperienceLevel, Job } from "../types";

export const EXPERIENCE_LABELS: Record<ExperienceLevel, string> = {
  junior: "Junior",
  middle: "Middle",
  senior: "Senior",
  lead: "Lead",
};

export const EMPLOYMENT_LABELS: Record<EmploymentType, string> = {
  full_day: "Полный день",
  part_time: "Частичная занятость",
  remote: "Удалённо",
};

export function formatSalary(job: Pick<Job, "salary_from" | "salary_to" | "currency">): string {
  const { salary_from, salary_to, currency } = job;
  if (!salary_from && !salary_to) return "З/п не указана";
  const fmt = (n: number) => n.toLocaleString("ru-RU");
  if (salary_from && salary_to) return `${fmt(salary_from)}–${fmt(salary_to)} ${currency}`;
  if (salary_from) return `от ${fmt(salary_from)} ${currency}`;
  return `до ${fmt(salary_to as number)} ${currency}`;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}
