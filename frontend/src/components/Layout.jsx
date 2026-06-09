import React from "react";
import { Header } from "./Header";
import { BottomNav } from "./BottomNav";
import { PopupNotice } from "./PopupNotice";
import AdSlot from "./AdSlot";

export const Layout = ({ children }) => {
  return (
    <div className="min-h-screen" style={{ background: "var(--cp-bg)" }}>
      <Header />
      {/* Header banner ad — direct sponsor first, AdSense fallback. Premium hidden. */}
      <div className="max-w-[1400px] mx-auto px-3 md:px-5 pt-2">
        <AdSlot placement="header_banner" minHeight={0}/>
      </div>
      <main className="max-w-[1400px] mx-auto px-3 md:px-5 py-4 pb-24 lg:pb-6" data-testid="app-main">
        {children}
      </main>
      <footer className="max-w-[1400px] mx-auto px-3 md:px-5 py-6 text-xs hidden lg:block" style={{ color: "var(--cp-text-muted)" }}>
        © 2026 Cloudy Pitch · Global Football, Predictions & Fantasy
      </footer>
      {/* Sticky mobile bottom banner — sits ABOVE the bottom nav. */}
      <div className="lg:hidden fixed left-0 right-0 z-20" style={{ bottom: 56 }}>
        <AdSlot placement="mobile_bottom" minHeight={0} className="mx-2"/>
      </div>
      <BottomNav />
      <PopupNotice />
    </div>
  );
};

export default Layout;
