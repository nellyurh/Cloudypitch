import React from "react";
import { Header } from "./Header";
import { BottomNav } from "./BottomNav";

export const Layout = ({ children }) => {
  return (
    <div className="min-h-screen" style={{ background: "var(--cp-bg)" }}>
      <Header />
      <main className="max-w-[1400px] mx-auto px-3 md:px-5 py-4 pb-24 lg:pb-6" data-testid="app-main">
        {children}
      </main>
      <footer className="max-w-[1400px] mx-auto px-3 md:px-5 py-6 text-xs hidden lg:block" style={{ color: "var(--cp-text-muted)" }}>
        © 2026 Cloudy Pitch · Global Football, Predictions & Fantasy
      </footer>
      <BottomNav />
    </div>
  );
};

export default Layout;
