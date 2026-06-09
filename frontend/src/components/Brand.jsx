import React, { useEffect, useState } from "react";
import api from "../lib/api";

// Global brand asset cache — loaded once on app boot, mutated by Admin.
let _brand = { mark: "/cp-mark.png", markUploaded: false, logo: null, logoDark: null, wordmark: null, favicon: null };
const _subs = new Set();
function _emit() { _subs.forEach(fn => fn(_brand)); _applyFavicon(); }

/** Replace all `<link rel="icon">` / `<link rel="apple-touch-icon">` tags in <head>
 *  with the admin-uploaded favicon. Falls back to the brand mark if no
 *  dedicated favicon was uploaded. */
function _applyFavicon() {
  if (typeof document === "undefined") return;
  const url = _brand.favicon || (_brand.markUploaded ? _brand.mark : null);
  if (!url) return;
  const head = document.head;
  head.querySelectorAll('link[rel="icon"], link[rel="apple-touch-icon"], link[rel="shortcut icon"]').forEach(l => l.remove());
  const link = document.createElement("link");
  link.rel = "icon";
  link.href = url;
  head.appendChild(link);
  const apple = document.createElement("link");
  apple.rel = "apple-touch-icon";
  apple.href = url;
  head.appendChild(apple);
}

export async function refreshBrand() {
  try {
    const { data } = await api.get("/brand");
    _brand = {
      mark: data.brand_mark_url || data.brand_logo_url || "/cp-mark.png",
      markUploaded: Boolean(data.brand_mark_url || data.brand_logo_url),
      logo: data.brand_logo_url || null,
      logoDark: data.brand_logo_dark_url || null,
      wordmark: data.brand_wordmark_url || null,
      favicon: data.brand_favicon_url || null,
    };
    _emit();
  } catch (_) {}
}

function _detectDark() {
  if (typeof document === "undefined") return false;
  // Respect explicit data-theme="dark" on <html>, else use prefers-color-scheme
  const html = document.documentElement;
  if (html.getAttribute("data-theme") === "dark") return true;
  if (html.classList.contains("dark")) return true;
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) return true;
  return false;
}

function useBrand() {
  const [b, setB] = useState(_brand);
  const [isDark, setIsDark] = useState(_detectDark());
  useEffect(() => {
    const fn = (next) => setB({ ...next });
    _subs.add(fn);
    if (!_brand.logo && !_brand.wordmark) refreshBrand();
    // Watch for theme changes
    const mq = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");
    const onTheme = () => setIsDark(_detectDark());
    if (mq) mq.addEventListener("change", onTheme);
    const obs = new MutationObserver(onTheme);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme"] });
    return () => { _subs.delete(fn); if (mq) mq.removeEventListener("change", onTheme); obs.disconnect(); };
  }, []);
  return { ...b, isDark, activeLogo: (isDark && b.logoDark) ? b.logoDark : b.logo };
}

/**
 * Cloudy Pitch brand kit.
 *
 *   <Brand />                — wordmark + mark (header default)
 *   <Brand variant="mark"/>  — mark only (favicon-style)
 *   <Brand variant="text"/>  — "CLOUDYPITCH" wordmark only
 *
 * If admins have uploaded a combined logo (`brand_logo_url`) we render that
 * directly; otherwise we fall back to the mark + text composition.
 */
export const Brand = ({ size = 30, variant = "logo", className = "" }) => {
  const b = useBrand();

  // If a combined logo upload exists, use it as a single image (preserves the
  // shipped design exactly as the admin uploaded it — no text appended).
  // Auto-switches between light and dark variants when both are uploaded.
  if (variant === "logo" && b.activeLogo) {
    // Render at the requested size; CSS clamps to a sensible max so we never
    // grow the header chrome. The image itself scales — not just its padding.
    const desktopH = Math.max(size * 2.2, 80);
    return (
      <img
        src={b.activeLogo}
        alt="Cloudy Pitch"
        className={`cp-brand-img ${className}`}
        style={{ "--cp-logo-h": `${desktopH}px` }}
        data-testid="cp-brand"
      />
    );
  }

  // If only a mark upload exists (and the admin treats it as the full brand),
  // render the mark alone WITHOUT the "CloudyPitch" text next to it.
  if (variant === "logo" && b.markUploaded) {
    return (
      <img
        src={b.mark}
        alt="Cloudy Pitch"
        className={className}
        style={{ height: size * 1.8, width: "auto", objectFit: "contain", display: "inline-block" }}
        data-testid="cp-brand"
      />
    );
  }

  if (variant === "mark") {
    return (
      <span className={`cp-brand-mark ${className}`} style={{ width: size, height: size }} data-testid="cp-brand-mark">
        <img src={b.mark} alt="Cloudy Pitch" style={{ width: "100%", height: "100%", objectFit: "contain" }}/>
      </span>
    );
  }

  if (variant === "text") {
    if (b.wordmark) {
      return (
        <img
          src={b.wordmark}
          alt="CloudyPitch"
          className={className}
          style={{ height: size * 0.55, width: "auto", objectFit: "contain", display: "inline-block" }}
          data-testid="cp-brand-text"
        />
      );
    }
    return (
      <span className={`cp-brand-text font-extrabold tracking-tight ${className}`} style={{ color: "var(--cp-lime, #A3E635)", fontSize: size * 0.55, lineHeight: 1 }} data-testid="cp-brand-text">
        CLOUDYPITCH
      </span>
    );
  }

  // Fallback: mark + text composition
  return (
    <div className={`flex items-center gap-2 ${className}`} data-testid="cp-brand">
      <span style={{ width: size, height: size, display: "inline-block" }}>
        <img src={b.mark} alt="" style={{ width: "100%", height: "100%", objectFit: "contain" }}/>
      </span>
      <span className="font-extrabold tracking-tight" style={{ color: "var(--cp-text)", fontSize: size * 0.5, lineHeight: 1, letterSpacing: "0.02em" }}>
        CloudyPitch
      </span>
    </div>
  );
};

/**
 * AnimatedBrand — pulsing/rotating mark used as loader.
 *   <AnimatedBrand size={72} label="Loading match…" />
 */
export const AnimatedBrand = ({ size = 72, label = null, className = "" }) => {
  const b = useBrand();
  return (
    <div className={`flex flex-col items-center justify-center gap-3 ${className}`} data-testid="cp-loader">
      <div className="cp-loader-wrap" style={{ width: size, height: size }}>
        <img
          src={b.mark}
          alt=""
          style={{ width: "100%", height: "100%", objectFit: "contain" }}
          className="cp-loader-spin"
        />
        <span className="cp-loader-pulse" style={{ width: size * 0.6, height: size * 0.6 }}/>
      </div>
      {label && (
        <div className="text-[10px] uppercase tracking-[0.3em]" style={{ color: "var(--cp-text-muted)" }}>{label}</div>
      )}
    </div>
  );
};

export default Brand;
