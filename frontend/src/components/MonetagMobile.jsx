import { useEffect } from "react";

/**
 * 📱 Monetag mobile ad loader — In-Page Push + Vignette Banner only.
 *
 * Both formats are admin-approved (non-popunder, non-onclick). They render:
 *  · In-Page Push → small slide-in notification ad (does NOT hijack first tap)
 *  · Vignette    → full-screen interstitial between page transitions
 *
 * Skipped entirely on:
 *  · Desktop viewports (>= 768px)
 *  · Premium users (no ads anywhere)
 *
 * Mounts once globally in <App/>. Snippets injected only once per page load.
 */
const MOBILE_SCRIPTS = [
  // In-Page Push (zone 11157495)
  { id: "monetag-mobile-inpage-push", zone: "11157495", src: "https://nap5k.com/tag.min.js" },
  // Vignette Banner (zone 11157502)
  { id: "monetag-mobile-vignette",   zone: "11157502", src: "https://n6wxm.com/vignette.min.js" },
];

export default function MonetagMobile({ isPremium = false }) {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (isPremium) return;
    if (window.innerWidth >= 768) return; // desktop — skip

    const injected = [];
    for (const s of MOBILE_SCRIPTS) {
      if (document.getElementById(s.id)) continue; // already injected
      const el = document.createElement("script");
      el.id = s.id;
      el.async = true;
      el.dataset.zone = s.zone;
      el.dataset.cfasync = "false";
      el.src = s.src;
      document.body.appendChild(el);
      injected.push(el);
    }
    // Cleanup on unmount (e.g., user upgrades to premium)
    return () => {
      for (const el of injected) {
        try { el.remove(); } catch { /* ignore */ }
      }
    };
  }, [isPremium]);

  return null;
}
