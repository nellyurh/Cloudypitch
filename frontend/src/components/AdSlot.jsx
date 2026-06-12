import React, { useEffect, useRef, useState } from "react";
import api from "../lib/api";

/**
 * AdSlot — renders the best ad for a placement via /api/ads/serve/{placement}.
 *
 *   <AdSlot placement="header_banner" />
 *   <AdSlot placement="sidebar_right" minHeight={250} />
 *   <AdSlot placement="match_list_inline" inline />
 *
 * Behavior:
 *   • Premium users → renders nothing (backend returns ad:null + premium:true).
 *   • Admin-created "direct" sponsor → image banner + click-through + impression count.
 *   • Else → AdSense slot if admin pasted a slot id; otherwise Auto Ads handle it.
 *
 * Backwards-compat: also accepts old `placementKey` prop name.
 */
const AdSlot = ({ placement, placementKey, className = "", style = {}, minHeight, inline = false, label = true }) => {
  const key = placement || placementKey;
  const [ad, setAd] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const insRef = useRef(null);

  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get(`/ads/serve/${key}`);
        if (cancelled) return;
        if (data?.premium) { setLoaded(true); return; }
        setAd(data?.ad || null);
      } catch (_e) { /* silent */ }
      setLoaded(true);
    })();
    return () => { cancelled = true; };
  }, [key]);

  // After AdSense fallback mounts, push the slot so Google can fill it.
  useEffect(() => {
    if (ad?.network !== "adsense" || !ad?.ad_slot) return;
    try {
      if (typeof window !== "undefined") {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
      }
    } catch (_e) { /* AdSense not yet loaded; auto-ads handle it */ }
  }, [ad]);

  // PropellerAds + Adsterra inline banners: the dashboard provides a
  // self-contained `<script src="..."></script>` snippet per zone. We mount
  // it into a div, then re-execute the <script> tag (innerHTML alone won't
  // run scripts).
  const propellerRef = useRef(null);
  useEffect(() => {
    if (!ad || !["propellerads", "adsterra"].includes(ad.network) || !propellerRef.current) return;
    const html = ad.snippet_html || "";
    if (!html) return;
    const container = propellerRef.current;
    container.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.innerHTML = html;
    Array.from(wrap.childNodes).forEach((node) => {
      if (node.tagName === "SCRIPT") {
        const s = document.createElement("script");
        for (const attr of node.attributes) s.setAttribute(attr.name, attr.value);
        if (node.textContent) s.textContent = node.textContent;
        container.appendChild(s);
      } else {
        container.appendChild(node);
      }
    });
    // Fire the snippet — impression counter already bumped on /ads/serve.
  }, [ad, key]);

  if (!loaded) {
    if (minHeight) return <div className={className} style={{ minHeight, ...style }} aria-hidden="true"/>;
    return null;
  }
  if (!ad || dismissed) return null;

  // Direct sponsor banner
  if (ad.network === "direct") {
    return (
      <a
        href={ad.target_url || "#"}
        target={ad.target_url ? "_blank" : undefined}
        rel="noopener noreferrer sponsored"
        onClick={(e) => {
          api.post(`/ads/click/${ad.id}`).catch(() => {});
          if (!ad.target_url) e.preventDefault();
        }}
        className={`block relative overflow-hidden rounded ${className}`}
        style={{ minHeight: minHeight || (inline ? 80 : 90), background: "var(--cp-surface)", ...style }}
        data-testid={`adslot-direct-${key}`}
      >
        {ad.sponsor_image_url && (
          <img src={ad.sponsor_image_url} alt={ad.sponsor_name || "Sponsored"} className="w-full h-full object-cover" loading="lazy"/>
        )}
        {label && (
          <span className="absolute top-1 left-1 text-[9px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded" style={{ background: "rgba(0,0,0,0.6)", color: "#fff" }}>
            Ad · {ad.sponsor_name || "Sponsor"}
          </span>
        )}
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); setDismissed(true); }}
          className="absolute top-1 right-1 text-[12px] leading-none w-5 h-5 rounded-full"
          style={{ background: "rgba(0,0,0,0.55)", color: "#fff" }}
          aria-label="Dismiss ad"
          data-testid={`adslot-dismiss-${key}`}
        >×</button>
      </a>
    );
  }

  // PropellerAds + Adsterra banner
  if (ad.network === "propellerads" || ad.network === "adsterra") {
    const w = ad.width || 300;
    const h = ad.height || 250;
    return (
      <div
        className={className}
        style={{ minHeight: minHeight || h, ...style }}
        data-testid={`adslot-${ad.network}-${key}`}
      >
        {label && <div className="text-[9px] uppercase tracking-widest mb-1 opacity-50">Ad</div>}
        <div
          ref={propellerRef}
          style={{ minHeight: h, minWidth: w, maxWidth: "100%", margin: "0 auto" }}
        />
      </div>
    );
  }

  // AdSense fallback
  if (ad.network === "adsense" && ad.publisher_id) {
    if (!ad.ad_slot) {
      // Auto Ads → render a tiny marker; the AdSense script handles the actual placement
      return <span data-testid={`adslot-auto-${key}`} className="hidden" aria-hidden="true"/>;
    }
    return (
      <div className={className} style={{ minHeight: minHeight || 90, ...style }} data-testid={`adslot-adsense-${key}`}>
        {label && <div className="text-[9px] uppercase tracking-widest mb-1 opacity-50">Advertisement</div>}
        <ins
          ref={insRef}
          className="adsbygoogle"
          style={{ display: "block" }}
          data-ad-client={ad.publisher_id}
          data-ad-slot={ad.ad_slot}
          data-ad-format="auto"
          data-full-width-responsive="true"
        />
      </div>
    );
  }

  return null;
};

export { AdSlot };
export default AdSlot;
