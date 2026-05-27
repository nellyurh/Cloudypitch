import React from "react";
import { Header } from "./Header";

export const Layout = ({ children }) => {
  return (
    <div className="min-h-screen" style={{ background: "var(--cp-bg)" }}>
      <Header />
      <main className="max-w-[1400px] mx-auto px-3 md:px-5 py-4" data-testid="app-main">
        {children}
      </main>
      <footer className="max-w-[1400px] mx-auto px-3 md:px-5 py-6 text-xs" style={{ color: "var(--cp-text-muted)" }}>
        © 2026 Cloudy Pitch · Built in Lagos · v1.0
      </footer>
    </div>
  );
};

export default Layout;
