import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import api from "../lib/api";

/**
 * Injects ad-network site verification snippets + Multitag serving script
 * into <head>. Splits behavior so Monetag's OnClick/Vignette can't hijack
 * the user's first tap on action pages:
 *
 *   verification_head (meta/link only): injected on EVERY page so the
 *     crawler verifier always sees the proof tag (also baked into
 *     index.html — this is a safety re-inject).
 *
 *   serving_head (scripts that fire ads): injected ONLY on browse routes
 *     (homepage, scores, matches, news). NEVER on click-sensitive routes:
 *       /my-teams, /build-team, /fantasy, /wc/games/*, /admin/*, /wallet,
 *       /signin, /signup, /predictions/new, /transfers
 *
 * The serving_head is torn down on route change so an in-progress ad
 * doesn't follow the user into an action page.
 */
const ACTION_ROUTE_PREFIXES = [
  // Only block ad-script injection on the dense squad-building page where
  // every tap is committed inventory. Every other route shows ads (with
  // OnClick/Vignette gated by the network's own frequency caps).
  "/build-team",
];

const TAG = "data-cp-ads-head";
const VERIFY_TAG = "verify";
const SERVE_TAG = "serve";

function isActionRoute(path) {
  if (!path) return false;
  return ACTION_ROUTE_PREFIXES.some((p) => path === p || path.startsWith(p + "/") || path.startsWith(p + "?"));
}

function mountSnippet(html, marker) {
  if (!html) return;
  const wrap = document.createElement("div");
  wrap.innerHTML = html;
  Array.from(wrap.childNodes).forEach((node) => {
    if (node.nodeType !== 1) return; // skip text nodes
    let target;
    if (node.tagName === "SCRIPT") {
      target = document.createElement("script");
      for (const attr of node.attributes) target.setAttribute(attr.name, attr.value);
      if (node.textContent) target.textContent = node.textContent;
    } else {
      target = node.cloneNode(true);
    }
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
  const location = useLocation();
  const path = location.pathname;

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const { data } = await api.get("/ads/config");
        if (!mounted) return;

        // Always (re)apply verification — safe meta tags only.
        unmount(VERIFY_TAG);
        mountSnippet(data?.propellerads_verification_head || "", VERIFY_TAG);

        // Conditionally apply serving script — never on action pages.
        unmount(SERVE_TAG);
        if (!isActionRoute(path)) {
          mountSnippet(data?.propellerads_serving_head || "", SERVE_TAG);
        }
      } catch (_e) { /* silent */ }
    })();
    return () => { mounted = false; };
  }, [path]);

  return null;
};

export default AdHeadInjector;
