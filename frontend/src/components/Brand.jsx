import React from "react";

/**
 * Cloudy Pitch brand kit.
 *
 *   <Brand />                — wordmark + triangle (header default)
 *   <Brand variant="mark"/>  — triangle only (favicon-style)
 *   <Brand variant="text"/>  — "CLOUDYPITCH" wordmark only
 *
 * Triangle artwork is provided as a PNG with a black background. We hide the
 * background by isolating the lime layer via CSS mix-blend-mode so the logo
 * sits on any surface cleanly.
 */
export const Brand = ({ size = 30, variant = "logo", className = "" }) => {
  if (variant === "mark") {
    return (
      <span className={`cp-brand-mark ${className}`} style={{ width: size, height: size }} data-testid="cp-brand-mark">
        <img src="/cp-mark.png" alt="Cloudy Pitch" style={{ width: "100%", height: "100%", objectFit: "contain", mixBlendMode: "screen" }}/>
      </span>
    );
  }
  if (variant === "text") {
    return (
      <span className={`cp-brand-text font-extrabold tracking-tight ${className}`} style={{ color: "var(--cp-lime, #A3E635)", fontSize: size * 0.55, lineHeight: 1 }} data-testid="cp-brand-text">
        CLOUDYPITCH
      </span>
    );
  }
  // Default: combined logo (mark + wordmark)
  return (
    <div className={`flex items-center gap-2 ${className}`} data-testid="cp-brand">
      <span style={{ width: size, height: size, display: "inline-block" }}>
        <img src="/cp-mark.png" alt="" style={{ width: "100%", height: "100%", objectFit: "contain", mixBlendMode: "screen" }}/>
      </span>
      <span className="font-extrabold tracking-tight" style={{ color: "var(--cp-text)", fontSize: size * 0.5, lineHeight: 1, letterSpacing: "0.02em" }}>
        CLOUDYPITCH
      </span>
    </div>
  );
};

/**
 * AnimatedBrand — pulsing/rotating triangle stack used as loader.
 *   <AnimatedBrand size={72} label="Loading match…" />
 */
export const AnimatedBrand = ({ size = 72, label = null, className = "" }) => (
  <div className={`flex flex-col items-center justify-center gap-3 ${className}`} data-testid="cp-loader">
    <div className="cp-loader-wrap" style={{ width: size, height: size }}>
      <img
        src="/cp-mark.png"
        alt=""
        style={{ width: "100%", height: "100%", objectFit: "contain", mixBlendMode: "screen" }}
        className="cp-loader-spin"
      />
      <span className="cp-loader-pulse" style={{ width: size * 0.6, height: size * 0.6 }}/>
    </div>
    {label && (
      <div className="text-[10px] uppercase tracking-[0.3em]" style={{ color: "var(--cp-text-muted)" }}>{label}</div>
    )}
  </div>
);

export default Brand;
