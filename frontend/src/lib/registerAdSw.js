/**
 * Ad service-worker management.
 *
 * 🚫 We intentionally DO NOT register Monetag/PropellerAds' service worker
 * at `/sw.js` any more. That worker (domain 3nbf4.com, zoneId 11139111)
 * hooks into navigation and `notificationclick` events, which acts as a
 * tap-hijack on the first user gesture — destroying UX.
 *
 * Instead we proactively *unregister* any previously-registered ad worker
 * + delete its caches so users who had it installed before the fix get
 * cleaned up the next time they open the site.
 */
const AD_SW_DOMAINS = ["3nbf4.com", "propellerads", "monetag"];

export function registerAdServiceWorker() {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;
  // Run an async cleanup pass — never await it, never block first paint.
  (async () => {
    try {
      const regs = await navigator.serviceWorker.getRegistrations();
      for (const reg of regs) {
        const scriptURL =
          (reg.active && reg.active.scriptURL) ||
          (reg.installing && reg.installing.scriptURL) ||
          (reg.waiting && reg.waiting.scriptURL) ||
          "";
        const isAdWorker =
          scriptURL.endsWith("/sw.js") ||
          AD_SW_DOMAINS.some((d) => scriptURL.includes(d));
        if (isAdWorker) {
          try { await reg.unregister(); } catch (_e) { /* noop */ }
        }
      }
      // Wipe any caches the ad worker left behind.
      if ("caches" in window) {
        try {
          const names = await caches.keys();
          await Promise.all(
            names
              .filter((n) => AD_SW_DOMAINS.some((d) => n.includes(d)) || /propellerads|monetag|adservice/i.test(n))
              .map((n) => caches.delete(n)),
          );
        } catch (_e) { /* noop */ }
      }
    } catch (_e) { /* sandboxed / private mode — ignore */ }
  })();
}
