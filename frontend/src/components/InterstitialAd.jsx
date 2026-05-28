import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import api from "../lib/api";
import { X } from "lucide-react";

const RATE_LIMIT_MS = 3 * 60 * 1000; // 3 minutes between interstitials
const STORAGE_KEY = "cp_interstitial_last_shown";
const DISMISS_KEY = "cp_interstitial_dismiss_count";

// Pages where interstitials should NEVER show (payment / checkout / signin flows)
const BLOCKED_PATHS = ["/payment", "/signin", "/signup", "/premium"];

/**
 * InterstitialAd — fullscreen modal triggered on route changes, rate-limited.
 * Free-tier users only. Skipped if user has dismissed >3 times in this session.
 */
export const InterstitialAd = () => {
  const location = useLocation();
  const [ad, setAd] = useState(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    setAd(null);
    setShown(false);
    // Rate-limit guard
    if (BLOCKED_PATHS.some(p => location.pathname.startsWith(p))) return;
    const last = parseInt(localStorage.getItem(STORAGE_KEY) || "0", 10);
    const now = Date.now();
    if (now - last < RATE_LIMIT_MS) return;
    const dismissCount = parseInt(localStorage.getItem(DISMISS_KEY) || "0", 10);
    if (dismissCount >= 3) return;

    // Delay a beat to avoid showing during page transition
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get("/ads/placements?placement_key=interstitial_nav");
        if (data.premium) return;
        if (data.placements && data.placements.length > 0) {
          const pick = data.placements[Math.floor(Math.random() * data.placements.length)];
          setAd(pick);
          setShown(true);
          localStorage.setItem(STORAGE_KEY, String(now));
          api.post(`/ads/impression/${pick.id}`).catch(() => {});
        }
      } catch (_) {}
    }, 800);
    return () => clearTimeout(t);
  }, [location.pathname]);

  if (!shown || !ad) return null;

  const onClick = (e) => {
    api.post(`/ads/click/${ad.id}`).catch(() => {});
    if (!ad.target_url) e.preventDefault();
  };
  const dismiss = () => {
    setShown(false);
    const c = parseInt(localStorage.getItem(DISMISS_KEY) || "0", 10);
    localStorage.setItem(DISMISS_KEY, String(c + 1));
  };

  return (
    <div className="fixed inset-0 z-[160] flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.85)" }} data-testid="interstitial-ad">
      <div className="relative max-w-md w-full">
        <button onClick={dismiss} className="absolute -top-10 right-0 text-white p-2 hover:bg-white/10 rounded" data-testid="interstitial-close">
          <X size={20}/>
        </button>
        <a
          href={ad.target_url || "#"}
          target={ad.target_url ? "_blank" : undefined}
          rel="noopener noreferrer"
          onClick={onClick}
          className="block cp-surface overflow-hidden"
          data-testid="interstitial-cta"
        >
          {ad.sponsor_image_url ? (
            <img src={ad.sponsor_image_url} alt={ad.sponsor_name || "Sponsor"} className="w-full"/>
          ) : (
            <div className="p-12 text-center">
              <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>SPONSORED · {ad.network.toUpperCase()}</div>
              <div className="text-2xl font-extrabold mt-2">{ad.sponsor_name || "Advertisement"}</div>
            </div>
          )}
          <div className="p-3 text-xs" style={{ color: "var(--cp-text-muted)" }}>
            SPONSORED · {ad.sponsor_name || "Direct"} · tap to continue
          </div>
        </a>
      </div>
    </div>
  );
};

export default InterstitialAd;
