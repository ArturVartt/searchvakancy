import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import {
  APPLICATION_STATUSES,
  APPLICATION_STATUS_LABELS,
  copyToClipboard,
  fillCoverLetter,
} from "../lib/applications";
import { markJobViewed } from "../lib/viewedJobs";
import type { ApplicationStatus, Job, ProfileSet } from "../types";

interface ApplyModalProps {
  job: Job;
  onClose: () => void;
  onSaved: (status: ApplicationStatus) => void;
}

const fieldClass =
  "w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]";

function CopyRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (await copyToClipboard(value)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <div className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2">
      <div className="min-w-0 flex-1">
        <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)]">{label}</div>
        <div className="break-all text-sm">{value}</div>
      </div>
      <button
        type="button"
        onClick={handleCopy}
        className="shrink-0 rounded-md bg-[var(--color-surface-hover)] px-2.5 py-1 text-xs font-medium hover:bg-[var(--color-border)]"
      >
        {copied ? "✓ Скопировано" : "Копировать"}
      </button>
    </div>
  );
}

export function ApplyModal({ job, onClose, onSaved }: ApplyModalProps) {
  const [loading, setLoading] = useState(true);
  const [sets, setSets] = useState<ProfileSet[]>([]);
  const [setId, setSetId] = useState<number | null>(null);
  const [status, setStatus] = useState<ApplicationStatus>("applied");
  const [note, setNote] = useState("");
  const [letter, setLetter] = useState("");
  const [letterCopied, setLetterCopied] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = sets.find((s) => s.id === setId) ?? null;

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listProfileSets(), api.getApplicationForJob(job.id)])
      .then(([setsPage, existing]) => {
        if (cancelled) return;
        const application = existing[0];
        setSets(setsPage.results);
        const initialSetId = application?.profile_set ?? setsPage.results[0]?.id ?? null;
        setSetId(initialSetId);
        if (application) {
          setStatus(application.status);
          setNote(application.note);
        }
        const initialSet = setsPage.results.find((s) => s.id === initialSetId);
        setLetter(initialSet ? fillCoverLetter(initialSet.cover_letter, job) : "");
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "Не удалось загрузить данные");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // Только job.id: live-обновление вакансии по WS не должно перезагружать форму и стирать ввод.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.id]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  function handleSetChange(id: number | null) {
    setSetId(id);
    const next = sets.find((s) => s.id === id);
    setLetter(next ? fillCoverLetter(next.cover_letter, job) : "");
  }

  async function save(nextStatus: ApplicationStatus): Promise<boolean> {
    setError(null);
    setPending(true);
    try {
      await api.saveApplication({ job_id: job.id, status: nextStatus, profile_set: setId, note });
      onSaved(nextStatus);
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не удалось сохранить отклик");
      return false;
    } finally {
      setPending(false);
    }
  }

  async function handleSaveOnly() {
    if (await save(status)) onClose();
  }

  // Ссылка открывается штатно (target=_blank) — так её не блокирует
  // попап-блокер, а сохранение отклика идёт параллельно в фоне.
  async function handleOpenAndApply() {
    markJobViewed(job.id);
    const nextStatus = status === "saved" ? "applied" : status;
    if (await save(nextStatus)) onClose();
  }

  async function handleCopyLetter() {
    if (await copyToClipboard(letter)) {
      setLetterCopied(true);
      setTimeout(() => setLetterCopied(false), 1500);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Отклик на вакансию"
        onClick={(e) => e.stopPropagation()}
        className="max-h-[92vh] w-full min-w-0 overflow-y-auto rounded-t-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 sm:max-w-lg sm:rounded-2xl sm:p-5"
      >
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold leading-snug">{job.title}</h2>
            <p className="text-sm text-[var(--color-text-muted)]">{job.company}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="-m-1 shrink-0 p-1 text-xl leading-none text-[var(--color-text-muted)]"
          >
            ×
          </button>
        </div>

        {loading ? (
          <p className="text-sm text-[var(--color-text-muted)]">Загрузка…</p>
        ) : (
          <div className="flex flex-col gap-3">
            {sets.length === 0 ? (
              <p className="rounded-lg border border-dashed border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
                Нет сетов профиля — контакты и резюме подставить неоткуда.{" "}
                <Link to="/profile-sets/new" className="text-[var(--color-accent)]">
                  Создать сет
                </Link>
              </p>
            ) : (
              <>
                <div>
                  <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Сет профиля</label>
                  <select
                    value={setId ?? ""}
                    onChange={(e) => handleSetChange(e.target.value ? Number(e.target.value) : null)}
                    className={fieldClass}
                  >
                    {sets.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>

                {selected && (
                  <div className="flex flex-col gap-2">
                    {selected.phone && <CopyRow label="Телефон" value={selected.phone} />}
                    {selected.email && <CopyRow label="Почта" value={selected.email} />}
                    {selected.github_url && <CopyRow label="GitHub" value={selected.github_url} />}
                    {selected.resume && (
                      <a
                        href={selected.resume}
                        target="_blank"
                        rel="noreferrer"
                        download
                        className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-center text-sm font-medium text-[var(--color-accent)] hover:bg-[var(--color-surface-hover)]"
                      >
                        ⬇ Скачать резюме
                      </a>
                    )}
                  </div>
                )}

                {selected && (
                  <div>
                    <div className="mb-1 flex items-center justify-between">
                      <label className="text-xs font-medium text-[var(--color-text-muted)]">
                        Сопроводительное письмо
                      </label>
                      {letter && (
                        <button
                          type="button"
                          onClick={handleCopyLetter}
                          className="rounded-md bg-[var(--color-surface-hover)] px-2.5 py-1 text-xs font-medium hover:bg-[var(--color-border)]"
                        >
                          {letterCopied ? "✓ Скопировано" : "Копировать"}
                        </button>
                      )}
                    </div>
                    <textarea
                      rows={5}
                      value={letter}
                      onChange={(e) => setLetter(e.target.value)}
                      placeholder="Шаблон письма не задан — добавьте его в сете профиля."
                      className={fieldClass}
                    />
                  </div>
                )}
              </>
            )}

            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Статус</label>
              <select value={status} onChange={(e) => setStatus(e.target.value as ApplicationStatus)} className={fieldClass}>
                {APPLICATION_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {APPLICATION_STATUS_LABELS[s]}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Заметка</label>
              <textarea
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Контакт рекрутера, вопросы, дата собеседования…"
                className={fieldClass}
              />
            </div>

            {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}

            <div className="flex flex-col gap-2 sm:flex-row">
              <a
                href={job.url}
                target="_blank"
                rel="noreferrer"
                onClick={handleOpenAndApply}
                className="flex-1 rounded-lg bg-[var(--color-accent)] px-3 py-2 text-center text-sm font-medium text-[var(--color-accent-contrast)] hover:bg-[var(--color-accent-hover)]"
              >
                Открыть вакансию и откликнуться →
              </a>
              <button
                type="button"
                onClick={handleSaveOnly}
                disabled={pending}
                className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm hover:bg-[var(--color-surface-hover)] disabled:opacity-50"
              >
                {pending ? "Сохранение…" : "Сохранить"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
