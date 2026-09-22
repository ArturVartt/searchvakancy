/**
 * "Просмотрено" — локально, per-browser (localStorage), не синхронизируется
 * между устройствами. Отмечаем просмотренной по клику "Открыть →" —
 * это самый однозначный сигнал намерения посмотреть вакансию.
 */
const STORAGE_KEY = "searchvakancy.viewedJobIds";
const DAY_MS = 24 * 60 * 60 * 1000;

function readViewedIds(): Set<number> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? new Set(JSON.parse(raw) as number[]) : new Set();
  } catch {
    return new Set();
  }
}

export function isJobViewed(jobId: number): boolean {
  return readViewedIds().has(jobId);
}

export function markJobViewed(jobId: number): void {
  try {
    const ids = readViewedIds();
    if (ids.has(jobId)) return;
    ids.add(jobId);
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
  } catch {
    // localStorage недоступен (приватный режим и т.п.) — просто не запоминаем
  }
}

/** Опубликована не позже суток назад. */
export function isPostedWithinLastDay(postedAt: string | null): boolean {
  if (!postedAt) return false;
  const posted = new Date(postedAt).getTime();
  if (Number.isNaN(posted)) return false;
  return Date.now() - posted <= DAY_MS;
}
