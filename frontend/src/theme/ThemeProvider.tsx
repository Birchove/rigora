import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  applyTheme,
  readPreference,
  resolvedTheme,
  writePreference,
  type Theme,
  type ThemePreference,
} from "./theme";

interface ThemeContextValue {
  theme: Theme;
  preference: ThemePreference;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreference] = useState<ThemePreference>(readPreference);
  const [, setSystemEpoch] = useState(0);
  const theme = resolvedTheme(preference);

  useEffect(() => {
    applyTheme(theme);
    if (preference !== "system") {
      return undefined;
    }
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (media === undefined) {
      return undefined;
    }
    const onChange = () => {
      applyTheme(resolvedTheme("system"));
      setSystemEpoch((value) => value + 1);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [preference, theme]);

  const toggleTheme = useCallback(() => {
    const next: Theme = resolvedTheme(preference) === "dark" ? "light" : "dark";
    writePreference(next);
    setPreference(next);
    applyTheme(next);
  }, [preference]);

  const value = useMemo(
    () => ({ theme, preference, toggleTheme }),
    [theme, preference, toggleTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext) ?? {
    theme: "light",
    preference: "system",
    toggleTheme: () => undefined,
  };
}
