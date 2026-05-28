import React, { useEffect, useState } from "react";
import api from "../lib/api";

/**
 * AdSlot — renders a single ad for a given placement_key.
 * Free-tier users only (server returns empty array for premium).
 * Networks: admob (script-based), adsense, meta (script-based), direct (sponsor image).
 * Premium subscribers see nothing.
 */
export const AdSlot = ({ placementKey, className = "" }) => {
  const [ad, setAd] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/ads/placements?placement_key=${placementKey}`);
        if (data.premium) return; // hide for premium
        if (data.placements && data.placements.length > 0) {
          // Weighted random pick
          const weighted = data.placements.flatMap(p => Array(Math.max(1, p.weight || 1)).fill(p));
          const pick = weighted[Math.floor(Math.random() * weighted.length)];
          setAd(pick);
          api.post(`/ads/impression/${pick.id}`).catch(() => {});
        }
      } catch (_) {}
    })();
  }, [placementKey]);

  if (!ad || dismissed) return null;

  const onClick = (e) => {
    api.post(`/ads/click/${ad.id}`).catch(() => {});
    if (!ad.target_url) e.preventDefault();
  };

  // Direct sponsorship — image banner
  if (ad.network === "direct") {
    return (
      <a
        href={ad.target_url || "#"}
        target={ad.target_url ? "_blank" : undefined}
        rel="noopener noreferrer"
        onClick={onClick}
        className={`block relative overflow-hidden rounded-lg ${className}`}
        data-testid={`ad-slot-${placementKey}`}
        style={{ background: "var(--cp-surface)" }}
      >
        {ad.sponsor_image_url && (
          <img src={ad.sponsor_image_url} alt={ad.sponsor_name || "Sponsor"} className="w-full h-full object-cover" />
        )}
        <span className="absolute top-1 left-1 cp-pill text-[9px]" style={{ background: "rgba(0,0,0,0.5)", color: "#fff" }}>SPONSORED · {ad.sponsor_name || "Direct"}</span>
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); setDismissed(true); }}
          className="absolute top-1 right-1 text-white/70 hover:text-white text-xs px-1"
          data-testid={`ad-dismiss-${placementKey}`}
        >×</button>
      </a>
    );
  }

  // Network-based ad (AdMob/AdSense/Meta) — placeholder script slot.
  // Production: drop in google-publisher-tag or appropriate SDK <ins> tag here.
  return (
    <div
      className={`relative rounded-lg overflow-hidden ${className}`}
      style={{ background: "var(--cp-surface-2)", minHeight: 80 }}
      data-testid={`ad-slot-${placementKey}`}
    >
      <div className="flex items-center justify-center h-full text-xs px-4 py-6" style={{ color: "var(--cp-text-muted)" }}>
        <span className="cp-pill text-[9px] mr-2" style={{ background: "rgba(0,0,0,0.3)", color: "var(--cp-text-muted)" }}>
          AD · {ad.network.toUpperCase()}
        </span>
        Advertisement
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="absolute top-1 right-1 text-xs px-1"
        style={{ color: "var(--cp-text-muted)" }}
        data-testid={`ad-dismiss-${placementKey}`}
      >×</button>
    </div>
  );
};

export default AdSlot;
