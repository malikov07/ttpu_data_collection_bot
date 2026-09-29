import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { en, type MessageKey } from "./en";
import { ru } from "./ru";
import { uz } from "./uz";

export type Lang = "uz" | "ru" | "en";
export const LANGS: { code: Lang; label: string }[] = [
  { code: "uz", label: "Oʻzbekcha" },
  { code: "ru", label: "Русский" },
  { code: "en", label: "English" },
];

const DICTS: Record<Lang, Record<MessageKey, string>> = { en, uz, ru };
const STORAGE_KEY = "ttpu.lang";
const LOCALES: Record<Lang, string> = { uz: "uz-UZ", ru: "ru-RU", en: "en-GB" };

function detect(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "uz" || saved === "ru" || saved === "en") return saved;
  } catch {
    /* storage unavailable */
  }
  const nav = navigator.language.slice(0, 2);
  return nav === "ru" || nav === "uz" ? nav : "en";
}

export type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string;

interface I18nValue {
  lang: Lang;
  locale: string;
  setLang: (lang: Lang) => void;
  t: Translate;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detect);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    document.documentElement.lang = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const t = useCallback<Translate>(
    (key, vars) => {
      let text = DICTS[lang][key] ?? en[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) text = text.replaceAll(`{${k}}`, String(v));
      return text;
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, locale: LOCALES[lang], setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n outside I18nProvider");
  return ctx;
}

export type { MessageKey };
