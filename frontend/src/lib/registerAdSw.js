/**
 * Register the PropellerAds push service worker at `/sw.js`.
 *
 * - Premium users (or anyone with `localStorage.cp_no_ads === "1"`) are
 *   skipped, so paying subs never see push prompts.
 * - We don't request notification permission here — we only register the
 *   worker; PropellerAds' worker code triggers the system prompt only
 *   when the user clicks something they routed (i.e. user-gesture).
 * - Wrapped in try/catch because some browsers (incognito Firefox, http
 *   contexts) reject SW registration.
 */
export function registerAdServiceWorker() {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;
  // Opt-out flag — set when the user buys premium.
  try {
    if (localStorage.getItem("cp_no_ads") === "1") return;
  } catch (_e) { /* sandboxed storage; treat as enabled */ }

  // Only register on https origins
  if (window.location.protocol !== "https:") return;

  // Defer to idle so we don't fight first-paint.
  const start = () => {
    try {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .catch(() => { /* silent — sw.js may not be configured yet */ });
    } catch (_e) { /* noop */ }
  };
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(start, { timeout: 4000 });
  } else {
    setTimeout(start, 2000);
  }
}
