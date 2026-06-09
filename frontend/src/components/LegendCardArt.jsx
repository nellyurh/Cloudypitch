import React from "react";

/**
 * LegendCardArt — Renders a sticker-style WC card matching the Cloudy Pitch design.
 *
 * Tiers (controls colors only — admin can map any legend card to any tier):
 *   • epic  → orange body + blue header band
 *   • elite → lime body + white header band with blue text
 *   • gold  → white body + gold gradient header band
 *
 * Props:
 *   tier          'epic' | 'elite' | 'gold' (default: 'epic')
 *   title         Card label shown in the header band (e.g. "EPIC CARD")
 *   heroImageUrl  Optional URL for the centre image. If empty, a stylised "26"
 *                 numeric badge is rendered (no FIFA trademarks reproduced).
 *   size          Pixel width — height is computed at 5:6 aspect ratio.
 *   className     Extra CSS.
 */
const TIER_STYLES = {
  epic:  {
    body: "#F25C1B",
    headerBand: "#3B5BFF",
    headerText: "#FFFFFF",
    centerBg: "#0B0B0F",
  },
  elite: {
    body: "#C9F44A",
    headerBand: "#FFFFFF",
    headerText: "#1B3CFF",
    centerBg: "#C9F44A",
  },
  gold:  {
    body: "#FFFFFF",
    headerBand: "linear-gradient(180deg, #FFE07A 0%, #BB8B2A 100%)",
    headerText: "#FFFFFF",
    centerBg: "#111111",
  },
};

export const LegendCardArt = ({
  tier = "epic",
  title,
  heroImageUrl,
  brandText = "CloudyPitch",
  size = 280,
  className = "",
  "data-testid": testId,
}) => {
  const s = TIER_STYLES[tier] || TIER_STYLES.epic;
  const labels = { epic: "EPIC CARD", elite: "ELITE CARD", gold: "GOLD CARD" };
  const label = title || labels[tier] || "CARD";

  return (
    <div
      className={`relative overflow-hidden ${className}`}
      style={{
        width: size,
        background: s.body,
        boxShadow: "0 8px 24px rgba(0,0,0,0.18)",
      }}
      data-testid={testId || `legend-card-${tier}`}
    >
      {/* Brand strip */}
      <BrandStrip text={brandText}/>

      {/* Inner card */}
      <div className="mx-3 mt-3 rounded-[14px] overflow-hidden" style={{ background: s.body, border: `2px solid rgba(255,255,255,0.7)` }}>
        {/* Tier banner */}
        <div className="px-4 py-2.5 text-center" style={{ background: s.headerBand }}>
          <span className="text-base md:text-lg font-extrabold tracking-wider" style={{ color: s.headerText, letterSpacing: "0.08em" }}>
            {label}
          </span>
        </div>
        {/* Hero artwork */}
        <div className="mx-4 my-4 rounded-md overflow-hidden flex items-center justify-center" style={{ background: s.centerBg, aspectRatio: "1 / 1" }}>
          {heroImageUrl ? (
            <img src={heroImageUrl} alt="" className="w-full h-full object-cover" loading="lazy"/>
          ) : (
            <StylizedTwentySix tier={tier}/>
          )}
        </div>
      </div>

      {/* Footer pattern */}
      <FooterPattern/>
    </div>
  );
};

const BrandStrip = ({ text }) => (
  <div className="grid grid-cols-[16px_1fr_16px] h-8" data-testid="brand-strip">
    <div style={{ background: "#5B17C9" }}/>
    <div className="flex items-center justify-center gap-1.5" style={{ background: "#C51616" }}>
      <span className="inline-block" style={{ width: 14, height: 14 }}>
        <svg viewBox="0 0 24 24" fill="#A3E635"><polygon points="12,2 22,8 18,22 6,22 2,8"/></svg>
      </span>
      <span className="text-[11px] font-extrabold tracking-wider" style={{ color: "#fff" }}>{text}</span>
    </div>
    <div style={{ background: "#C9F44A" }}/>
  </div>
);

const FooterPattern = () => (
  <svg viewBox="0 0 200 30" preserveAspectRatio="none" className="block w-full" style={{ height: 30 }} aria-hidden="true">
    <defs>
      <clipPath id="cp-card-foot"><rect width="200" height="30"/></clipPath>
    </defs>
    <g clipPath="url(#cp-card-foot)">
      <rect x="0" y="22" width="40" height="8" fill="#FBC02D"/>
      <rect x="40" y="22" width="80" height="8" fill="#A3E635"/>
      <rect x="120" y="22" width="80" height="8" fill="#1AAE9F"/>
      <circle cx="20" cy="18" r="14" fill="#1A2EB8"/>
      <circle cx="55" cy="18" r="14" fill="#5B17C9"/>
      <circle cx="90" cy="18" r="14" fill="#1A2EB8"/>
      <circle cx="125" cy="18" r="14" fill="#5B17C9"/>
      <circle cx="155" cy="18" r="14" fill="#3CCFB0"/>
      <circle cx="185" cy="18" r="14" fill="#A3E635"/>
    </g>
  </svg>
);

/**
 * Stylised "26" hero — placeholder used when no admin-supplied hero image is
 * configured. Intentionally distinct from any third-party trademarks so the
 * card looks complete out-of-the-box; admins can replace with a real WC asset
 * via the legend-card admin form's `hero_image_url` field.
 */
const StylizedTwentySix = ({ tier }) => {
  const stroke = tier === "elite" ? "#1B3CFF" : "#FFFFFF";
  return (
    <svg viewBox="0 0 200 200" className="w-3/4 h-3/4">
      <text x="50%" y="58%" textAnchor="middle" dominantBaseline="middle" fontFamily="Inter, sans-serif" fontWeight="900" fontSize="140" fill="none" stroke={stroke} strokeWidth="6">
        26
      </text>
      <text x="50%" y="88%" textAnchor="middle" dominantBaseline="middle" fontFamily="Inter, sans-serif" fontWeight="900" fontSize="22" fill={stroke}>
        WORLD CUP
      </text>
    </svg>
  );
};

export default LegendCardArt;
