import React, { useMemo, useState } from "react";
import { Star, ShieldCheck } from "lucide-react";

/**
 * FPL-style pitch team view.
 *
 * Props:
 *   players      : [{ player_id, name, position, team_id, points, captain, vice,
 *                     image_path?, club_logo? }]
 *   formation    : "4-3-3" | "4-4-2" | "3-5-2" | … (string)
 *   captainId    : the captain player_id (optional, derives from `players` if missing)
 *   viceId       : vice captain player_id (optional)
 *   benchBoost   : bool — shows BB chip on header
 *   topStats     : optional { average, your_score, highest, label } header strip
 *   subtitle     : small text below the score header
 */

const POSITION_LABELS = ["GK", "DEF", "MID", "FWD"];

function parseFormation(formation, players) {
  // Default: derive from positions
  const buckets = { GK: [], DEF: [], MID: [], FWD: [] };
  for (const p of players || []) {
    const pos = (p.position || "MID").toUpperCase();
    if (buckets[pos]) buckets[pos].push(p);
    else buckets.MID.push(p);
  }
  return buckets;
}

function pointsTone(pts) {
  if (pts == null) return { bg: "rgba(148,163,184,0.18)", fg: "#CBD5E1" };
  if (pts >= 8)  return { bg: "rgba(163,230,53,0.20)", fg: "#A3E635" };
  if (pts >= 3)  return { bg: "rgba(125,211,252,0.18)", fg: "#7DD3FC" };
  if (pts >= 1)  return { bg: "rgba(251,191,36,0.18)", fg: "#FBBF24" };
  if (pts === 0) return { bg: "rgba(251,191,36,0.10)", fg: "#94A3B8" };
  return { bg: "rgba(239,68,68,0.18)", fg: "#EF4444" };
}

function flagUrl(country, size = 80) {
  if (!country) return null;
  // Generic country flag CDN (matches BuildTeam.jsx convention)
  const c = country.toLowerCase().replace(/[^a-z]/g, "-");
  return `https://flagcdn.com/${size}x60/${c.slice(0, 2)}.png`;
}

function PlayerTile({ p }) {
  const tone = pointsTone(p.points);
  const photo = p.photo_url || p.image_path || p.profile_pic || p.photo;
  const flag = flagUrl(p.country, 80);
  const cap = p.captain;
  const vice = p.vice;
  const size = 56;
  return (
    <div className="flex flex-col items-center gap-0.5 w-[64px] md:w-[78px] shrink-0" data-testid={`pitch-tile-${p.player_id}`}>
      <div className="relative" style={{ width: size, height: size }}>
        <span
          className="absolute inset-0 rounded-full overflow-hidden flex items-center justify-center"
          style={{
            background: photo ? "#fff" : "#A3E635",
            boxShadow: "0 2px 6px rgba(0,0,0,0.25), inset 0 0 0 2px rgba(255,255,255,0.9)",
          }}
        >
          {photo ? (
            <img
              src={photo}
              alt={p.name || ""}
              loading="lazy"
              style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top center" }}
              onError={(e) => { e.currentTarget.style.display = "none"; }}
            />
          ) : (
            <span className="text-cp-forest font-extrabold text-base">
              {(p.name || "?").split(" ").slice(-1)[0].slice(0, 1).toUpperCase()}
            </span>
          )}
        </span>
        {flag && (
          <img
            src={flag}
            alt=""
            className="absolute"
            style={{
              left: -2, bottom: -2, width: 20, height: 14,
              objectFit: "cover", borderRadius: 3,
              border: "1.5px solid #fff", boxShadow: "0 1px 3px rgba(0,0,0,0.4)",
            }}
            onError={(e) => { e.currentTarget.style.display = "none"; }}
          />
        )}
        {cap && (
          <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full text-[10px] font-extrabold flex items-center justify-center ring-1 ring-white"
                style={{ background: "#A3E635", color: "#0C2A14" }}
                title="Captain">C</span>
        )}
        {!cap && vice && (
          <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full text-[10px] font-extrabold flex items-center justify-center ring-1 ring-white"
                style={{ background: "#7DD3FC", color: "#0B2638" }}
                title="Vice-captain">V</span>
        )}
      </div>
      <div className="w-full text-center text-[10px] font-bold truncate px-0.5 mt-1 text-white drop-shadow"
           title={p.name}>
        {(p.name || "—").split(" ").slice(-1)[0]}
      </div>
      <div className="w-full text-center rounded-sm py-0.5 text-[11px] font-extrabold tabular-nums"
           style={{ background: tone.bg, color: tone.fg }}
           data-testid={`pitch-points-${p.player_id}`}>
        {p.points != null ? p.points : "—"}
      </div>
    </div>
  );
}

function Row({ players }) {
  if (!players?.length) return null;
  return (
    <div className="flex items-start justify-center gap-2 md:gap-4 px-2">
      {players.map((p) => <PlayerTile key={p.player_id} p={p} />)}
    </div>
  );
}

export default function PitchTeamView({
  players = [], formation = "4-3-3", captainId, viceId, benchBoost,
  topStats, subtitle, footer,
}) {
  // Apply cap/vice if not already on rows
  const decorated = useMemo(() => players.map((p) => ({
    ...p,
    captain: p.captain ?? (captainId && p.player_id === captainId),
    vice:    p.vice    ?? (viceId    && p.player_id === viceId),
  })), [players, captainId, viceId]);

  const buckets = parseFormation(formation, decorated);

  return (
    <div className="relative rounded-lg overflow-hidden" data-testid="pitch-team-view">
      {/* Pitch background */}
      <div
        className="absolute inset-0 pointer-events-none"
        aria-hidden
        style={{
          background:
            "linear-gradient(to bottom, #1F3A1B 0%, #285821 30%, #1F4E1B 60%, #16401A 100%)",
        }}
      />
      {/* Pitch lines (svg overlay) */}
      <svg aria-hidden viewBox="0 0 320 480" preserveAspectRatio="none"
           className="absolute inset-0 w-full h-full opacity-40 pointer-events-none">
        <rect x="4" y="4" width="312" height="472" fill="none" stroke="white" strokeWidth="1"/>
        <line x1="0" y1="240" x2="320" y2="240" stroke="white" strokeWidth="1"/>
        <circle cx="160" cy="240" r="34" fill="none" stroke="white" strokeWidth="1"/>
        <rect x="80"  y="4"  width="160" height="56" fill="none" stroke="white" strokeWidth="1"/>
        <rect x="80" y="420" width="160" height="56" fill="none" stroke="white" strokeWidth="1"/>
        <rect x="124" y="4"   width="72" height="22" fill="none" stroke="white" strokeWidth="1"/>
        <rect x="124" y="454" width="72" height="22" fill="none" stroke="white" strokeWidth="1"/>
      </svg>

      {/* Header strip */}
      {topStats && (
        <div className="relative z-10 grid grid-cols-3 gap-2 px-3 pt-3 pb-2 text-center">
          <div>
            <div className="text-[9px] uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.65)" }}>Average</div>
            <div className="text-lg font-extrabold tabular-nums text-white">{topStats.average ?? "—"}</div>
          </div>
          <div>
            <div className="text-[9px] uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.65)" }}>{topStats.label || "Your Score"}</div>
            <div className="text-2xl font-black tabular-nums text-white">{topStats.your_score ?? "—"}</div>
          </div>
          <div>
            <div className="text-[9px] uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.65)" }}>Highest</div>
            <div className="text-lg font-extrabold tabular-nums text-white">{topStats.highest ?? "—"}</div>
          </div>
        </div>
      )}
      {subtitle && (
        <div className="relative z-10 text-center text-[10px] font-bold uppercase tracking-widest pb-2" style={{ color: "rgba(255,255,255,0.65)" }}>
          {subtitle}
        </div>
      )}
      {benchBoost && (
        <div className="relative z-10 flex justify-center pb-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold"
                style={{ background: "rgba(251,191,36,0.85)", color: "#3a2c00" }}
                data-testid="bench-boost-chip">
            <ShieldCheck size={11}/> Bench Boost ×1.5
          </span>
        </div>
      )}

      {/* Pitch rows */}
      <div className="relative z-10 py-3 space-y-4">
        <Row players={buckets.GK} />
        <Row players={buckets.DEF} />
        <Row players={buckets.MID} />
        <Row players={buckets.FWD} />
      </div>

      {footer && <div className="relative z-10 px-3 py-2 border-t border-white/10">{footer}</div>}
    </div>
  );
}

/* ───────────────────────────────────────────────────────────────────────
 * DaySlider — horizontal swipeable day picker for the main-team viewer.
 * ─────────────────────────────────────────────────────────────────────── */
export function DaySlider({ days = [], activeIndex = 0, onChange }) {
  if (!days.length) return null;
  return (
    <div className="cp-surface !bg-transparent ring-1 ring-white/5 rounded-lg p-2 mb-3" data-testid="day-slider">
      <div className="flex gap-1 overflow-x-auto scroll-smooth snap-x snap-mandatory pb-1">
        {days.map((d, i) => {
          const active = i === activeIndex;
          const date = new Date(d.date);
          const label = date.toLocaleDateString([], { day: "2-digit", month: "short" });
          return (
            <button
              key={d.date}
              onClick={() => onChange && onChange(i)}
              className={`snap-start shrink-0 px-3 py-1.5 rounded-md text-center transition ${active ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`}
              style={!active ? { color: "var(--cp-text)" } : undefined}
              data-testid={`day-tab-${d.date}`}
            >
              <div className="text-[10px] uppercase tracking-wider opacity-80">{label}</div>
              <div className="text-sm font-extrabold tabular-nums">{d.points} pts</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
