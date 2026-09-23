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
      className="rounded-lg border border-[var(--color-border)] px-2 py-1 text-xs hover:bg-[var(--color-surface-hover)] sm:px-2.5 sm:py-1.5 sm:text-sm"
    >
      {theme === "light" ? "🌙" : "☀️"}
    </button>
  );
}

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `shrink-0 whitespace-nowrap rounded-lg px-2 py-1 text-xs font-medium transition-colors sm:px-3 sm:py-1.5 sm:text-sm ${
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
          <div className="flex items-center gap-2 sm:gap-3">
            <NavLink to="/" className="shrink-0 text-base font-bold text-[var(--color-text)] sm:text-lg">
              SearchVakancy
            </NavLink>

            {stats && (
              <span className="hidden truncate text-xs text-[var(--color-text-muted)] sm:inline">
                {stats.total_active} активных · +{stats.new_today} сегодня
              </span>
            )}

            <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
              <ThemeToggle />
              {isAuthenticated ? (
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-lg border border-[var(--color-border)] px-2 py-1 text-xs hover:bg-[var(--color-surface-hover)] sm:px-3 sm:py-1.5 sm:text-sm"
                >
                  Выйти
                </button>
              ) : (
                <NavLink
                  to="/login"
                  className="rounded-lg bg-[var(--color-accent)] px-2 py-1 text-xs font-medium text-[var(--color-accent-contrast)] hover:bg-[var(--color-accent-hover)] sm:px-3 sm:py-1.5 sm:text-sm"
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
          <nav className="-mx-4 mt-1.5 flex items-center gap-1 overflow-x-auto px-4 scrollbar-none sm:mt-2">
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
