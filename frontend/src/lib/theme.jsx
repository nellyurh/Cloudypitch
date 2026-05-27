import React, { createContext, useContext, useEffect, useState } from "react";

const ThemeCtx = createContext(null);

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("cp-theme") : null;
    return saved || "dark";
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    try { localStorage.setItem("cp-theme", theme); } catch (_) {}
  }, [theme]);

  return (
    <ThemeCtx.Provider value={{ theme, setTheme, toggle: () => setTheme(t => t === "dark" ? "light" : "dark") }}>
      {children}
    </ThemeCtx.Provider>
  );
};

export const useTheme = () => useContext(ThemeCtx);
