import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../lib/api";

export function ProfileSetFormPage() {
  const { id } = useParams<{ id: string }>();
  const isEdit = id !== undefined;
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [resume, setResume] = useState<File | null>(null);
  const [existingResumeUrl, setExistingResumeUrl] = useState<string | null>(null);

  const [loading, setLoading] = useState(isEdit);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isEdit) return;
    api
      .getProfileSet(Number(id))
      .then((set) => {
        setName(set.name);
        setPhone(set.phone);
        setEmail(set.email);
        setGithubUrl(set.github_url);
        setExistingResumeUrl(set.resume);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Не удалось загрузить сет профиля"))
      .finally(() => setLoading(false));
  }, [id, isEdit]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      if (isEdit) {
        await api.updateProfileSet(Number(id), {
          name,
          phone,
          email,
          github_url: githubUrl,
          ...(resume ? { resume } : {}),
        });
      } else {
        await api.createProfileSet({ name, phone, email, github_url: githubUrl, resume });
      }
      navigate("/profile-sets");
    } catch (err) {
      if (err instanceof ApiError) {
        const body = err.body as Record<string, string[]> | null;
        setError(body?.resume?.[0] ?? body?.name?.[0] ?? err.message);
      } else {
        setError("Что-то пошло не так");
      }
    } finally {
      setPending(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-[var(--color-text-muted)]">Загрузка…</p>;
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="mb-4 text-xl font-semibold">{isEdit ? "Изменить сет профиля" : "Новый сет профиля"}</h1>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5"
      >
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Название сета</label>
          <input
            required
            autoFocus
            placeholder="Frontend RU, Backend EN…"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Телефон</label>
          <input
            type="tel"
            placeholder="+7 999 123-45-67"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Почта</label>
          <input
            type="email"
            placeholder="me@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">Ссылка на GitHub</label>
          <input
            type="url"
            placeholder="https://github.com/username"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
            Резюме (PDF, DOC, DOCX)
          </label>
          {existingResumeUrl && !resume && (
            <a
              href={existingResumeUrl}
              target="_blank"
              rel="noreferrer"
              className="mb-1 block truncate text-xs text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
            >
              Текущий файл — открыть
            </a>
          )}
          <input
            required={!isEdit}
            type="file"
            accept=".pdf,.doc,.docx"
            onChange={(e) => setResume(e.target.files?.[0] ?? null)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm outline-none file:mr-3 file:rounded file:border-0 file:bg-[var(--color-surface-hover)] file:px-2 file:py-1 file:text-sm focus:border-[var(--color-accent)]"
          />
          {isEdit && (
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">Оставьте пустым, чтобы не менять файл.</p>
          )}
        </div>

        {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}

        <div className="mt-1 flex gap-2">
          <button
            type="submit"
            disabled={pending}
            className="flex-1 rounded-lg bg-[var(--color-accent)] px-3 py-2 text-sm font-medium text-[var(--color-accent-contrast)] hover:bg-[var(--color-accent-hover)] disabled:opacity-50"
          >
            {pending ? "Сохранение…" : isEdit ? "Сохранить" : "Создать"}
          </button>
          <button
            type="button"
            onClick={() => navigate("/profile-sets")}
            className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
          >
            Отмена
          </button>
        </div>
      </form>
    </div>
  );
}
