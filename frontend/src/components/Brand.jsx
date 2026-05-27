import React from "react";

// Cloudy Pitch brand logo: lime "cp" circle + wordmark
export const Brand = ({ size = 32, withWord = true }) => (
  <div className="flex items-center gap-2" data-testid="cp-brand">
    <span
      className="cp-logo-circle"
      style={{ width: size, height: size, fontSize: size * 0.42 }}
    >
      cp
    </span>
    {withWord && (
      <span className="font-extrabold text-[15px] tracking-tight" style={{ color: "var(--cp-text)" }}>
        Cloudy Pitch
      </span>
    )}
  </div>
);

export default Brand;
