import React from "react";
import { Header } from "./Header";
import { BottomNav } from "./BottomNav";
import { PopupNotice } from "./PopupNotice";
import AdSlot from "./AdSlot";
import DailyDropWatcher from "./DailyDropWatcher";
import { Toaster as SonnerToaster } from "./ui/sonner";

export const Layout = ({ children }) => {
  // Hide ad chrome on the build-team page (heavy squad picker — every tap matters).
  const path = typeof window !== "undefined" ? window.location.pathname : "";
  const hideAds = path.startsWith("/build-team");
  return (
    <div className="min-h-screen" style={{ background: "var(--cp-bg)" }}>
      <Header />
      {/* Mobile-only sticky banner just under the sport-nav (top of viewport). */}
      {!hideAds && (
        <div className="lg:hidden sticky top-0 z-30" data-testid="mobile-top-banner">
          <div className="bg-cp-surface/95 backdrop-blur-sm border-b" style={{ borderColor: "var(--cp-border)" }}>
            <AdSlot placement="mobile_bottom" minHeight={0} className="mx-2 my-1"/>
          </div>
        </div>
      )}
      <main className="max-w-[1400px] mx-auto px-3 md:px-5 py-4 pb-24 lg:pb-6" data-testid="app-main">
        {children}
        {/* Desktop-only bottom-of-page banner. */}
        {!hideAds && (
          <div className="hidden lg:block mt-6" data-testid="desktop-bottom-banner">
            <AdSlot placement="leaderboard_above" minHeight={0}/>
          </div>
        )}
      </main>
      <footer className="max-w-[1400px] mx-auto px-3 md:px-5 py-6 text-xs hidden lg:block" style={{ color: "var(--cp-text-muted)" }}>
        © 2026 Cloudy Pitch · Global Football, Predictions & Fantasy
      </footer>
      {/* Sticky mobile bottom banner — sits ABOVE the bottom nav. */}
      {!hideAds && (
        <div className="lg:hidden fixed left-0 right-0 z-20" style={{ bottom: 56 }}>
          <AdSlot placement="mobile_bottom" minHeight={0} className="mx-2"/>
        </div>
      )}
      <BottomNav />
      <PopupNotice />
      <DailyDropWatcher />
      <SonnerToaster />
    </div>
  );
};

export default Layout;
