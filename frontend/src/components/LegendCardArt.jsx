import React from "react";

/**
 * LegendCardArt — Premium FUT/FIFA-inspired collectible card.
 *
 * Each tier is a distinct visual identity (not a recolor of one frame):
 *   • gold  → black + radiating gold rays, ornate serif "GOAT" treatment
 *   • elite → emerald holographic foil + chrome silver edge
 *   • epic  → crimson-magma lava gradient + faceted bronze frame
 *
 * Props:
 *   tier          'epic' | 'elite' | 'gold' (default: 'epic')
 *   title         Player/card name (header label)
 *   heroImageUrl  Optional URL for the centre image. Falls back to WC26 emblem.
 *   rating        1-99 numeric rating shown top-left FUT-style (default derived)
 *   position      Short pos code top-left (e.g. "ST"). Default per tier.
 *   size          Pixel width — height is rendered at 5:7 FUT aspect ratio.
 *   className     Extra CSS.
 *   data-testid   For tests.
 */

const TIER_DEFAULTS = {
  gold:  { rating: 99, position: "GOAT" },
  elite: { rating: 92, position: "ELITE" },
  epic:  { rating: 86, position: "STAR" },
};

const DEFAULT_HERO = "https://customer-assets.emergentagent.com/job_fantasy-wc/artifacts/gbyjrmxz_world-cup-2026-logo.webp";

export const LegendCardArt = ({
  tier = "epic",
  title,
  heroImageUrl,
  rating,
  position,
  brandText = "CLOUDYPITCH",
  size = 280,
  className = "",
  "data-testid": testId,
}) => {
  const t = TIER_DEFAULTS[tier] || TIER_DEFAULTS.epic;
  const r = rating ?? t.rating;
  const pos = position ?? t.position;
  const hero = heroImageUrl || DEFAULT_HERO;
  // FUT-card aspect ratio ~ 5:7
  const w = size;
  const h = Math.round(size * 1.4);
  // Scale internal typography & spacing to the requested width (base 280)
  const k = size / 280;

  const Card = tier === "gold" ? GoldCard : tier === "elite" ? EliteCard : EpicCard;

  return (
    <div
      className={`relative select-none ${className}`}
      style={{
        width: w,
        height: h,
        perspective: 1200,
        filter: "drop-shadow(0 18px 28px rgba(0,0,0,0.55))",
      }}
      data-testid={testId || `legend-card-${tier}`}
    >
      <Card w={w} h={h} k={k} rating={r} position={pos} title={title || tier.toUpperCase()} hero={hero} brandText={brandText}/>
    </div>
  );
};

/* ────────────────────────────  SHARED LAYOUT  ──────────────────────────── */

/**
 * The classic FUT layout, but tier-specific colors are passed in.
 * Children slot in the tier-specific background SVG behind the layout grid.
 */
const FutFrame = ({ w, h, k, rating, position, title, hero, brandText,
  textColor, mutedColor, accentColor, bgChildren, sheenColor, statColor, statLabels = ["PAC", "SHO", "PAS", "DRI", "DEF", "PHY"], stats, frameBorder, headerInside }) => {
  const ratingFont = Math.round(46 * k);
  const posFont = Math.round(14 * k);
  const titleFont = Math.round(18 * k);
  const statValueFont = Math.round(14 * k);
  const statLabelFont = Math.round(9 * k);
  const brandFont = Math.round(9 * k);
  const PAD = Math.round(14 * k);

  // Default randomized-but-stable stats from rating
  const ratingNum = Number(rating) || 85;
  const baseStats = stats || [
    ratingNum - 1, ratingNum + 2, ratingNum - 3, ratingNum + 1, ratingNum - 8, ratingNum - 4,
  ].map((v) => Math.max(50, Math.min(99, v)));

  return (
    <div
      className="relative overflow-hidden"
      style={{
        width: w,
        height: h,
        borderRadius: Math.round(18 * k),
        border: frameBorder,
        color: textColor,
      }}
    >
      {/* Tier-specific background art */}
      <div className="absolute inset-0">{bgChildren}</div>

      {/* Diagonal sheen sweep — present on every tier (color tuned per tier) */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `linear-gradient(115deg, transparent 30%, ${sheenColor} 50%, transparent 70%)`,
          mixBlendMode: "screen",
          opacity: 0.55,
        }}
      />

      {/* Subtle film grain via SVG noise */}
      <NoiseLayer/>

      {/* Top row: rating + position (left), nation/wc emblem (right) */}
      <div className="absolute z-20 flex items-start justify-between"
        style={{ top: PAD, left: PAD + 2, right: PAD + 2 }}>
        <div className="flex flex-col items-center" style={{ lineHeight: 1 }}>
          <span style={{
            fontFamily: "'Cinzel', 'Playfair Display', Georgia, serif",
            fontWeight: 900, fontSize: ratingFont, color: textColor,
            textShadow: `0 2px 0 rgba(0,0,0,0.35), 0 0 ${10 * k}px ${accentColor}66`,
            letterSpacing: "-0.02em",
          }}>{ratingNum}</span>
          <span style={{
            fontFamily: "'Cinzel', 'Playfair Display', Georgia, serif",
            fontWeight: 700, fontSize: posFont, color: textColor,
            letterSpacing: "0.18em", marginTop: 2 * k,
          }}>{position}</span>
          <span style={{
            display: "block", width: 28 * k, height: 1, marginTop: 4 * k,
            background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
          }}/>
          {headerInside}
        </div>

        {/* Top-right tier emblem */}
        <TierEmblem k={k} accentColor={accentColor} textColor={textColor}/>
      </div>

      {/* Hero portrait area */}
      <div className="absolute z-10 left-0 right-0 flex items-center justify-center"
        style={{ top: Math.round(38 * k), height: Math.round(180 * k) }}>
        <div
          className="relative"
          style={{
            width: Math.round(180 * k),
            height: Math.round(180 * k),
            borderRadius: "50%",
            background: `radial-gradient(circle at 50% 45%, ${accentColor}33 0%, transparent 65%)`,
          }}
        >
          <img src={hero} alt=""
            style={{
              width: "78%", height: "78%", objectFit: "contain", objectPosition: "center",
              position: "absolute", inset: "11%",
              filter: `drop-shadow(0 6px 10px rgba(0,0,0,0.5)) drop-shadow(0 0 ${14 * k}px ${accentColor}55)`,
            }}
            loading="lazy"
          />
        </div>
      </div>

      {/* Title (player/card name) */}
      <div className="absolute z-20 left-0 right-0 text-center"
        style={{ top: Math.round(228 * k) }}>
        <span style={{
          fontFamily: "'Cinzel', 'Playfair Display', Georgia, serif",
          fontWeight: 800, fontSize: titleFont, color: textColor,
          letterSpacing: "0.08em",
          textShadow: "0 1px 0 rgba(0,0,0,0.4)",
          textTransform: "uppercase",
        }}>{title}</span>
      </div>
      {/* Decorative line under name */}
      <div className="absolute z-20"
        style={{
          top: Math.round(254 * k), left: "25%", right: "25%", height: 1,
          background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
        }}
      />

      {/* Stats — FUT layout: 3 cols x 2 rows */}
      <div className="absolute z-20 grid grid-cols-3 gap-y-1.5 gap-x-3"
        style={{
          left: PAD + 14, right: PAD + 14, top: Math.round(266 * k),
          color: statColor || textColor,
        }}>
        {baseStats.map((v, i) => (
          <div key={i} className="flex items-center justify-center gap-1.5">
            <span style={{
              fontFamily: "'Cinzel', 'Playfair Display', Georgia, serif",
              fontWeight: 800, fontSize: statValueFont, color: textColor,
              textShadow: "0 1px 0 rgba(0,0,0,0.35)",
            }}>{v}</span>
            <span style={{
              fontSize: statLabelFont, color: mutedColor, letterSpacing: "0.1em", fontWeight: 700,
            }}>{statLabels[i]}</span>
          </div>
        ))}
      </div>

      {/* Brand wordmark — bottom */}
      <div className="absolute z-20 left-0 right-0 text-center"
        style={{ bottom: Math.round(10 * k) }}>
        <span style={{
          fontSize: brandFont, letterSpacing: "0.36em", fontWeight: 700,
          color: mutedColor,
        }}>{brandText} · WC26</span>
      </div>
    </div>
  );
};

/* ────────────────────────────  TIER: GOLD (GOAT)  ──────────────────────────── */

const GoldCard = ({ w, h, k, rating, position, title, hero, brandText }) => (
  <FutFrame
    w={w} h={h} k={k} rating={rating} position={position} title={title} hero={hero} brandText={brandText}
    textColor="#FFE9A6"
    mutedColor="#9B7C2E"
    accentColor="#FFC23A"
    sheenColor="rgba(255, 220, 120, 0.18)"
    statColor="#FFD46A"
    frameBorder="1px solid rgba(255, 217, 102, 0.55)"
    bgChildren={<GoldBackground k={k}/>}
  />
);

const GoldBackground = ({ k: _k }) => (
  <>
    {/* Base inky black with subtle purple */}
    <div className="absolute inset-0" style={{
      background: "radial-gradient(circle at 50% 35%, #2A1B05 0%, #110A02 55%, #060300 100%)",
    }}/>
    {/* Gold radial rays */}
    <svg viewBox="0 0 280 392" preserveAspectRatio="none" className="absolute inset-0 w-full h-full">
      <defs>
        <radialGradient id="goldGlow" cx="50%" cy="36%" r="60%">
          <stop offset="0%" stopColor="#FFD86E" stopOpacity="0.55"/>
          <stop offset="55%" stopColor="#B5811C" stopOpacity="0.15"/>
          <stop offset="100%" stopColor="#000" stopOpacity="0"/>
        </radialGradient>
        <linearGradient id="goldRay" x1="50%" y1="0%" x2="50%" y2="100%">
          <stop offset="0%" stopColor="#FFE08C" stopOpacity="0"/>
          <stop offset="50%" stopColor="#FFD66B" stopOpacity="0.18"/>
          <stop offset="100%" stopColor="#FFD66B" stopOpacity="0"/>
        </linearGradient>
      </defs>
      <rect width="280" height="392" fill="url(#goldGlow)"/>
      {/* radiating rays from focal point */}
      <g style={{ mixBlendMode: "screen" }}>
        {Array.from({ length: 14 }).map((_, i) => {
          const angle = (i / 14) * 360;
          return (
            <rect key={i} x="138" y="-40" width="4" height="240" fill="url(#goldRay)"
              transform={`rotate(${angle} 140 140)`}/>
          );
        })}
      </g>
    </svg>
    {/* Inner ornate border */}
    <div className="absolute" style={{
      top: 8, left: 8, right: 8, bottom: 8,
      borderRadius: 14,
      border: "1px solid rgba(255, 217, 102, 0.35)",
      boxShadow: "inset 0 0 22px rgba(255, 200, 80, 0.18), inset 0 0 0 1px rgba(0,0,0,0.4)",
    }}/>
    {/* Corner filigree */}
    <CornerFiligree color="#E8B956"/>
  </>
);

/* ────────────────────────────  TIER: ELITE  ──────────────────────────── */

const EliteCard = ({ w, h, k, rating, position, title, hero, brandText }) => (
  <FutFrame
    w={w} h={h} k={k} rating={rating} position={position} title={title} hero={hero} brandText={brandText}
    textColor="#F3FFE7"
    mutedColor="#88C0A0"
    accentColor="#5EF59D"
    sheenColor="rgba(170, 255, 220, 0.22)"
    statColor="#C8FFD7"
    frameBorder="1px solid rgba(150, 230, 200, 0.55)"
    bgChildren={<EliteBackground k={k}/>}
  />
);

const EliteBackground = ({ k: _k }) => (
  <>
    {/* Deep emerald background */}
    <div className="absolute inset-0" style={{
      background: "linear-gradient(165deg, #0A3D2F 0%, #07241B 55%, #051711 100%)",
    }}/>
    {/* Holographic angled stripes */}
    <svg viewBox="0 0 280 392" preserveAspectRatio="none" className="absolute inset-0 w-full h-full"
      style={{ mixBlendMode: "screen", opacity: 0.5 }}>
      <defs>
        <linearGradient id="holoStripe" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#5EF59D"/>
          <stop offset="33%" stopColor="#5EE0F5"/>
          <stop offset="66%" stopColor="#A55EF5"/>
          <stop offset="100%" stopColor="#5EF59D"/>
        </linearGradient>
        <pattern id="holoPattern" x="0" y="0" width="60" height="60" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">
          <rect width="6" height="60" fill="url(#holoStripe)" opacity="0.35"/>
          <rect x="22" width="2" height="60" fill="url(#holoStripe)" opacity="0.25"/>
        </pattern>
      </defs>
      <rect width="280" height="392" fill="url(#holoPattern)"/>
    </svg>
    {/* Chrome silver edge */}
    <div className="absolute" style={{
      top: 6, left: 6, right: 6, bottom: 6,
      borderRadius: 14,
      border: "1px solid",
      borderImage: "linear-gradient(135deg, #E6FFE9 0%, #6FB29A 30%, #1E3A2F 60%, #C8F0D5 100%) 1",
      boxShadow: "inset 0 0 18px rgba(94, 245, 157, 0.18)",
    }}/>
    {/* Star burst behind portrait */}
    <svg viewBox="0 0 280 392" preserveAspectRatio="none" className="absolute inset-0 w-full h-full" style={{ mixBlendMode: "screen" }}>
      <g transform="translate(140 128)">
        <polygon points="0,-60 14,-18 60,-18 22,8 36,52 0,28 -36,52 -22,8 -60,-18 -14,-18"
          fill="rgba(94,245,157,0.07)" stroke="rgba(94,245,157,0.35)" strokeWidth="0.6"/>
      </g>
    </svg>
    <CornerFiligree color="#5EF59D"/>
  </>
);

/* ────────────────────────────  TIER: EPIC (STAR)  ──────────────────────────── */

const EpicCard = ({ w, h, k, rating, position, title, hero, brandText }) => (
  <FutFrame
    w={w} h={h} k={k} rating={rating} position={position} title={title} hero={hero} brandText={brandText}
    textColor="#FFEAD0"
    mutedColor="#C58C5A"
    accentColor="#FF7A2A"
    sheenColor="rgba(255, 180, 120, 0.22)"
    statColor="#FFD0A0"
    frameBorder="1px solid rgba(255, 160, 90, 0.55)"
    bgChildren={<EpicBackground k={k}/>}
  />
);

const EpicBackground = ({ k: _k }) => (
  <>
    {/* Crimson-magma gradient */}
    <div className="absolute inset-0" style={{
      background: "radial-gradient(ellipse at 50% 30%, #FF5A1A 0%, #B8260F 38%, #4A0A0A 80%, #1B0303 100%)",
    }}/>
    {/* Cracked lava lines */}
    <svg viewBox="0 0 280 392" preserveAspectRatio="none" className="absolute inset-0 w-full h-full" style={{ opacity: 0.45, mixBlendMode: "screen" }}>
      <defs>
        <linearGradient id="lavaCrack" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#FFD66B"/>
          <stop offset="100%" stopColor="#FF3A2A"/>
        </linearGradient>
      </defs>
      <g stroke="url(#lavaCrack)" strokeWidth="1" fill="none">
        <path d="M 0 110 Q 60 120 100 90 T 200 130 T 280 100"/>
        <path d="M 0 220 Q 80 260 140 230 T 280 250"/>
        <path d="M 0 320 Q 90 290 160 320 T 280 310"/>
        <path d="M 40 50 L 80 90 L 70 130 L 110 160"/>
        <path d="M 200 60 L 230 90 L 220 130 L 250 160"/>
      </g>
    </svg>
    {/* Faceted bronze frame inner */}
    <div className="absolute" style={{
      top: 8, left: 8, right: 8, bottom: 8,
      borderRadius: 14,
      border: "1px solid rgba(255, 160, 90, 0.5)",
      boxShadow: "inset 0 0 22px rgba(255, 120, 60, 0.22), inset 0 0 0 1px rgba(0,0,0,0.45)",
    }}/>
    {/* Glow halo behind portrait */}
    <div className="absolute" style={{
      top: "16%", left: "50%", transform: "translateX(-50%)",
      width: "62%", height: "32%",
      background: "radial-gradient(ellipse at center, rgba(255, 160, 60, 0.55) 0%, transparent 70%)",
      filter: "blur(8px)",
    }}/>
    <CornerFiligree color="#FF9B4A"/>
  </>
);

/* ────────────────────────────  DECORATIONS  ──────────────────────────── */

const TierEmblem = ({ k, accentColor, textColor }) => (
  <div style={{
    width: Math.round(38 * k),
    height: Math.round(38 * k),
    borderRadius: "50%",
    background: `radial-gradient(circle at 35% 30%, ${accentColor}, ${accentColor}55 60%, transparent 100%)`,
    border: `1px solid ${accentColor}88`,
    boxShadow: `0 0 ${10 * k}px ${accentColor}66`,
    display: "flex", alignItems: "center", justifyContent: "center",
  }}>
    {/* Tiny star */}
    <svg viewBox="0 0 24 24" width={Math.round(18 * k)} height={Math.round(18 * k)} fill={textColor}>
      <polygon points="12,2 14.7,9 22,9.2 16.2,13.7 18.4,21 12,16.7 5.6,21 7.8,13.7 2,9.2 9.3,9"/>
    </svg>
  </div>
);

const CornerFiligree = ({ color }) => (
  <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 280 392" preserveAspectRatio="none">
    {/* Four corner ornaments */}
    {[
      { x: 14, y: 14, rot: 0 },
      { x: 266, y: 14, rot: 90 },
      { x: 14, y: 378, rot: 270 },
      { x: 266, y: 378, rot: 180 },
    ].map((c, i) => (
      <g key={i} transform={`translate(${c.x} ${c.y}) rotate(${c.rot})`} stroke={color} strokeWidth="0.8" fill="none" opacity="0.65">
        <path d="M 0 0 L 16 0 M 0 0 L 0 16 M 4 4 L 12 4 L 12 12"/>
        <circle cx="0" cy="0" r="1.6" fill={color}/>
      </g>
    ))}
  </svg>
);

const NoiseLayer = () => (
  <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ opacity: 0.08, mixBlendMode: "overlay" }}>
    <filter id="cp-card-noise">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/>
      <feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 1 0"/>
    </filter>
    <rect width="100%" height="100%" filter="url(#cp-card-noise)"/>
  </svg>
);

export default LegendCardArt;
