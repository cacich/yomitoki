import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import en from "./en.json";
import zhTW from "./zh-TW.json";

export const LOCALES = { "zh-TW": zhTW, en } as const;
export type Locale = keyof typeof LOCALES;
type Vars = Record<string, string | number>;

const STORAGE_KEY = "yomitoki.locale";

type Dict = { [k: string]: string | Dict };

export function lookup(dict: Dict, key: string): string | undefined {
  let node: string | Dict | undefined = dict;
  for (const part of key.split(".")) {
    if (typeof node !== "object" || node === null) return undefined;
    node = node[part];
  }
  return typeof node === "string" ? node : undefined;
}

export function format(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));
}

type Ctx = { locale: Locale; setLocale: (l: Locale) => void; t: (key: string, vars?: Vars) => string };
const I18nContext = createContext<Ctx | null>(null);

function initialLocale(): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && saved in LOCALES) return saved as Locale;
  } catch {
    /* 無法讀取 localStorage 時用預設值 */
  }
  return navigator.language.toLowerCase().startsWith("zh") ? "zh-TW" : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* 記不住也沒關係 */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale === "zh-TW" ? "zh-Hant" : "en";
  }, [locale]);

  const t = useCallback(
    (key: string, vars?: Vars) => {
      const text = lookup(LOCALES[locale] as Dict, key) ?? lookup(LOCALES["zh-TW"] as Dict, key);
      if (text === undefined) {
        if (import.meta.env.DEV) console.warn(`[i18n] missing key: ${key}`);
        return key;
      }
      return format(text, vars);
    },
    [locale],
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n 必須在 I18nProvider 裡使用");
  return ctx;
}

export const useT = () => useI18n().t;
