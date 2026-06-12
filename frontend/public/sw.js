/**
 * Cloudy Pitch — no-op service worker.
 *
 * Previously this file booted the Monetag/PropellerAds push worker
 * (domain 3nbf4.com, zoneId 11139111). That worker hijacked the user's
 * first tap on every page, so it's been removed.
 *
 * This stub remains so any browser that already registered the old
 * worker (or any HTML still referencing `/sw.js`) gets a clean,
 * inert replacement that does nothing on install/activate/fetch.
 *
 * It also self-unregisters on activate, completing the cleanup.
 */
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    try {
      // Clear out any caches the previous ad worker may have created.
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    } catch (_e) { /* noop */ }
    try {
      // Take control of any existing pages so the unregister actually applies.
      await self.clients.claim();
      await self.registration.unregister();
    } catch (_e) { /* noop */ }
  })());
});

// Explicitly NO `notificationclick`, `push`, or `fetch` handler — those
// were the hooks the ad network used to hijack taps.
