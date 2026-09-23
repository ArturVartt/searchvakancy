import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";
import { applyTheme, getStoredTheme, type Theme } from "../lib/theme";
import { api } from "../lib/api";
import type { Stats } from "../types";

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => getStoredTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return (
    <button
      type="button"
      onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
      aria-label="Переключить тему"
      className="rounded-lg border border-[var(--color-border)] px-2.5 py-1.5 text-sm hover:bg-[var(--color-surface-hover)]"
    >
      {theme === "light" ? "🌙" : "☀️"}
    </button>
  );
}

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `shrink-0 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors ${
    isActive
      ? "bg-[var(--color-accent)] text-[var(--color-accent-contrast)]"
      : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
  }`;

export function Layout() {
  const { isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    api.getStats().then(setStats).catch(() => setStats(null));
  }, []);

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-[var(--color-border)] bg-[var(--color-surface)]/90 backdrop-blur">
        <div className="w-full px-4 py-3">
          {/* Верхний ряд — лого, статистика и кнопки — всегда в одну строку
              на любой ширине экрана (умещается даже на 320px). Нав-ссылки
              вынесены в отдельный ряд ниже вместо flex-wrap на общем
              контейнере — иначе при 2-3 пунктах меню на телефоне порядок
              переноса строк было не предсказать и не проверить руками. */}
          <div className="flex items-center gap-3">
            <NavLink to="/" className="shrink-0 text-lg font-bold text-[var(--color-text)]">
              SearchVakancy
            </NavLink>

            {stats && (
              <span className="hidden truncate text-xs text-[var(--color-text-muted)] sm:inline">
                {stats.total_active} активных · +{stats.new_today} сегодня
              </span>
            )}

            <div className="ml-auto flex shrink-0 items-center gap-2">
              <ThemeToggle />
              {isAuthenticated ? (
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm hover:bg-[var(--color-surface-hover)]"
                >
                  Выйти
                </button>
              ) : (
                <NavLink
                  to="/login"
                  className="rounded-lg bg-[var(--color-accent)] px-3 py-1.5 text-sm font-medium text-[var(--color-accent-contrast)] hover:bg-[var(--color-accent-hover)]"
                >
                  Войти
                </NavLink>
              )}
            </div>
          </div>

          {/* Второй ряд — сами ссылки навигации. overflow-x-auto — подстраховка
              на очень узких экранах при большом числе пунктов (сейчас их 4
              для авторизованных — Вакансии/Избранное/Уведомления/Сеты
              профиля), а не основной механизм. */}
          <nav className="-mx-4 mt-2 flex items-center gap-1 overflow-x-auto px-4 scrollbar-none">
            <NavLink to="/" end className={navLinkClass}>
              Вакансии
            </NavLink>
            {isAuthenticated && (
              <>
                <NavLink to="/favorites" className={navLinkClass}>
                  Избранное
                </NavLink>
                <NavLink to="/notifications" className={navLinkClass}>
                  Уведомления
                </NavLink>
                <NavLink to="/profile-sets" className={navLinkClass}>
                  Сеты профиля
                </NavLink>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
