import type { ApplicationStatus } from "../types";

export const APPLICATION_STATUSES: ApplicationStatus[] = ["saved", "applied", "interview", "offer", "rejected"];

export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  saved: "Сохранено",
  applied: "Откликнулся",
  interview: "Собеседование",
  offer: "Оффер",
  rejected: "Отказ",
};

export const APPLICATION_STATUS_CLASSES: Record<ApplicationStatus, string> = {
  saved: "bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]",
  applied: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  interview: "bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-300",
  offer: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
  rejected: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};

// Подставляет {компания}/{должность} (и английские {company}/{title}) в
// шаблон сопроводительного письма. Неизвестные {плейсхолдеры} остаются как есть.
export function fillCoverLetter(template: string, job: { company: string; title: string }): string {
  return template.replace(/\{(компания|должность|company|title)\}/gi, (_, key: string) => {
    const k = key.toLowerCase();
    return k === "компания" || k === "company" ? job.company : job.title;
  });
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
