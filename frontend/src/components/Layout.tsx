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
  `rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
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
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-4 py-3">
          <NavLink to="/" className="mr-2 text-lg font-bold text-[var(--color-text)]">
            SearchVakancy
          </NavLink>
          <nav className="flex items-center gap-1">
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
              </>
            )}
          </nav>

          {stats && (
            <span className="ml-1 hidden text-xs text-[var(--color-text-muted)] sm:inline">
              {stats.total_active} активных · +{stats.new_today} сегодня
            </span>
          )}

          <div className="ml-auto flex items-center gap-2">
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
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
