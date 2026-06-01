import React, { useEffect, useState } from "react";
import api from "../lib/api";

// Global brand asset cache — loaded once on app boot, mutated by Admin.
let _brand = { mark: "/cp-mark.png", markUploaded: false, logo: null, wordmark: null };
const _subs = new Set();
function _emit() { _subs.forEach(fn => fn(_brand)); }

export async function refreshBrand() {
  try {
    const { data } = await api.get("/brand");
    _brand = {
      mark: data.brand_mark_url || data.brand_logo_url || "/cp-mark.png",
      markUploaded: Boolean(data.brand_mark_url || data.brand_logo_url),
      logo: data.brand_logo_url || null,
      wordmark: data.brand_wordmark_url || null,
    };
    _emit();
  } catch (_) {}
}

function useBrand() {
  const [b, setB] = useState(_brand);
  useEffect(() => {
    const fn = (next) => setB({ ...next });
    _subs.add(fn);
    if (!_brand.logo && !_brand.wordmark) refreshBrand();
    return () => _subs.delete(fn);
  }, []);
  return b;
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
  if (variant === "logo" && b.logo) {
    return (
      <img
        src={b.logo}
        alt="Cloudy Pitch"
        className={className}
        style={{ height: size * 1.8, width: "auto", objectFit: "contain", display: "inline-block" }}
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
