import { useEffect } from "react";
import api from "../lib/api";

/**
 * Injects ad-network site verification snippets (PropellerAds Multitag) into
 * <head> on every page. We re-parse and execute any <script> tags so push /
 * popunder loaders run, and append <meta> tags directly so the verifier can
 * scrape them on first paint.
 *
 * Mounted once at the App root. The snippet HTML is loaded from
 * /api/ads/config and admin-editable via Admin → Ads → "PropellerAds site
 * verification".
 */
export const AdHeadInjector = () => {
  useEffect(() => {
    let mounted = true;
    const TAG = "data-cp-ads-head";
    (async () => {
      try {
        const { data } = await api.get("/ads/config");
        if (!mounted) return;
        const html = (data && data.propellerads_verification_head) || "";
        // Tear down any previously injected nodes so the snippet stays in sync.
        document.head
          .querySelectorAll(`[${TAG}="propellerads"]`)
          .forEach((n) => n.parentNode && n.parentNode.removeChild(n));
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
          target.setAttribute(TAG, "propellerads");
          document.head.appendChild(target);
        });
      } catch (_e) { /* silent — verification optional */ }
    })();
    return () => { mounted = false; };
  }, []);
  return null;
};

export default AdHeadInjector;
