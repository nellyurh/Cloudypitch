import { useEffect, useState } from "react";
import api from "./api";

/* Global service-status hook.
 *
 * Reads `/api/services/status` (no auth) and exposes per-service flags
 * + shutdown reasons. Cached at module scope so a single in-flight fetch
 * is shared across components, refreshed every 60s for slow drift.
 */
let _cache = null;
let _pending = null;
const _subs = new Set();

function broadcast() {
  for (const fn of _subs) {
    try { fn(_cache); } catch { /* ignore */ }
  }
}

async function fetchStatus() {
  if (_pending) return _pending;
  _pending = api.get("/services/status")
    .then(({ data }) => {
      _cache = data || {};
      broadcast();
      return _cache;
    })
    .catch(() => {
      _cache = { fantasy: { enabled: true }, predictions: { enabled: true } };
      broadcast();
      return _cache;
    })
    .finally(() => { _pending = null; });
  return _pending;
}

// Auto-refresh in the background every 60s so admin toggles propagate quickly.
let _interval = null;
function startInterval() {
  if (_interval) return;
  _interval = setInterval(fetchStatus, 60_000);
}

export function refreshServiceStatus() {
  _cache = null;
  return fetchStatus();
}

export function useServiceStatus() {
  const [state, setState] = useState(_cache);
  useEffect(() => {
    _subs.add(setState);
    if (!_cache) fetchStatus();
    startInterval();
    return () => { _subs.delete(setState); };
  }, []);
  return state || { fantasy: { enabled: true }, predictions: { enabled: true } };
}
