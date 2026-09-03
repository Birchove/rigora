export const THEME_STORAGE_KEY = "rigora-theme";

export type Theme = "light" | "dark";
export type ThemePreference = Theme | "system";

export function readPreference(): ThemePreference {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY);
    if (value === "light" || value === "dark" || value === "system") {
      return value;
    }
  } catch {
    // private mode / tests
  }
  return "system";
}

export function writePreference(preference: ThemePreference): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // private mode / tests
  }
}

export function systemPrefersDark(): boolean {
  return globalThis.matchMedia?.("(prefers-color-scheme: dark)").matches === true;
}

export function resolvedTheme(preference: ThemePreference): Theme {
  if (preference === "system") {
    return systemPrefersDark() ? "dark" : "light";
  }
  return preference;
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  const themeColor = theme === "dark" ? "#10211a" : "#f5f5f7";
  let meta = document.querySelector('meta[name="theme-color"]');
  if (meta === null) {
    meta = document.createElement("meta");
    meta.setAttribute("name", "theme-color");
    document.head.append(meta);
  }
  meta.setAttribute("content", themeColor);
}
