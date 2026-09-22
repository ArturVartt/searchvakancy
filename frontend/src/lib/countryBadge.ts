/**
 * Единственный не-российский источник сейчас — IT-Jobs.uz (Узбекистан).
 * Явный текстовый бейдж, а не флаг-эмодзи: на Windows (Segoe UI Emoji)
 * флаги стран исторически рендерятся не картинкой, а как два обычных
 * символа кода страны ("UZ" вместо 🇺🇿) — выглядит как опечатка, а не как
 * бейдж. Проверено на скриншоте вживую (22.09.2026).
 */
export interface CountryBadge {
  label: string;
  className: string;
}

const REGIONAL_BADGES: Record<string, CountryBadge> = {
  "IT-Jobs.uz": { label: "UZ", className: "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300" },
};

export function sourceBadge(sourceName: string): CountryBadge | null {
  return REGIONAL_BADGES[sourceName] ?? null;
}
