import { useEffect } from "react";
import api from "../lib/api";

/**
 * AdHeadInjector — injects ONLY safe, verifier-required meta/link tags into
 * <head>. The Monetag/PropellerAds `serving_head` (OnClick/Vignette/
 * Interstitial/Popunder) scripts are NEVER injected anywhere on the site —
 * they hijacked the user's first tap and forced redirects.
 *
 * Inline banner ads still render via `<AdSlot>` on individual placements;
 * those are visual-only and do NOT intercept taps.
 *
 * If we ever need to re-enable a click-style ad format, do it via a
 * narrowly-scoped opt-in component, not a global <head> injection.
 */
const TAG = "data-cp-ads-head";
const VERIFY_TAG = "verify";

function mountSnippet(html, marker) {
  if (!html) return;
  const wrap = document.createElement("div");
  wrap.innerHTML = html;
  Array.from(wrap.childNodes).forEach((node) => {
    if (node.nodeType !== 1) return;
    // 🚫 Hard guard: never inject <script> tags via AdHeadInjector. Only
    // safe meta/link/comment nodes are allowed — they identify the site to
    // ad-network verifiers but cannot execute JavaScript.
    if (node.tagName === "SCRIPT") return;
    const target = node.cloneNode(true);
    target.setAttribute(TAG, marker);
    document.head.appendChild(target);
  });
}

function unmount(marker) {
  document.head
    .querySelectorAll(`[${TAG}="${marker}"]`)
    .forEach((n) => n.parentNode && n.parentNode.removeChild(n));
}

export const AdHeadInjector = () => {
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const { data } = await api.get("/ads/config");
        if (!mounted) return;
        // Always (re)apply verification — safe meta tags only (no scripts).
        unmount(VERIFY_TAG);
        mountSnippet(data?.propellerads_verification_head || "", VERIFY_TAG);
      } catch (_e) { /* silent */ }
    })();
    return () => { mounted = false; };
  }, []);

  return null;
};

export default AdHeadInjector;
