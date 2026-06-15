import React, { useEffect, useState } from "react";

const POSITION_ROW = {
  goalkeeper: 1,
  defender: 2,
  midfielder: 3,
  attacker: 4,
  forward: 4,
};

/**
 * Compute pitch positions for one team's starters.
 *
 * The function returns two numbers per player:
 *   · `depth` — 0 (own goal) to 1 (centre line). The CALLER decides whether
 *     to map this to x (landscape) or y (portrait/mobile).
 *   · `lane`  — 0 (left wing) to 1 (right wing).
 */
function computePositions(starters) {
  if (!starters || starters.length === 0) return [];
  const rows = {};
  starters.forEach((p) => {
    const code = (p.position_code || "").toLowerCase();
    const row = POSITION_ROW[code] || 3;
    if (!rows[row]) rows[row] = [];
    rows[row].push(p);
  });
  Object.values(rows).forEach((arr) => {
    arr.sort((a, b) => {
      const ga = a.grid != null ? Number(a.grid) : 999;
      const gb = b.grid != null ? Number(b.grid) : 999;
      return ga - gb;
    });
  });
  const rowKeys = Object.keys(rows).map(Number).sort((a, b) => a - b);
  const maxRow = Math.max(...rowKeys, 4);
  const minRow = Math.min(...rowKeys, 1);
  const denom = Math.max(1, maxRow - minRow);
  const out = [];
  rowKeys.forEach((row) => {
    const arr = rows[row];
    const depth = (row - minRow) / denom; // 0…1
    arr.forEach((p, i) => {
      const lane = (i + 0.5) / arr.length; // 0…1
      out.push({ player: p, depth, lane });
    });
  });
  return out;
}

function PlayerChip({ player, color, size = "md" }) {
  const rating = typeof player.rating === "number" ? player.rating : null;
  const xg = typeof player.xg === "number" && player.xg > 0 ? player.xg : null;
  const ratingColor =
    rating == null ? null
    : rating >= 8 ? "#A3E635"
    : rating >= 7 ? "#FBBF24"
    : rating >= 6 ? "#94A3B8" : "#FB7185";
  const dim = size === "lg" ? "w-10 h-10 text-[13px]" : size === "sm" ? "w-7 h-7 text-[10px]" : "w-9 h-9 text-[12px]";
  return (
    <div className="flex flex-col items-center pointer-events-auto">
      <div className="relative">
        <div
          className={`${dim} rounded-full flex items-center justify-center font-extrabold tabular-nums shadow-md ring-2 ring-black/40`}
          style={{ background: color, color: "#0a0a0a" }}
        >
          {player.player_number ?? "?"}
        </div>
        {rating != null && (
          <span
            className="absolute -top-1 -right-1 text-[9px] font-extrabold px-1 rounded shadow"
            style={{ background: ratingColor, color: "#0a0a0a" }}
            data-testid={`rating-${player.player_name}`}
          >{rating.toFixed(1)}</span>
        )}
        {xg != null && (
          <span
            className="absolute -bottom-1 -left-1 text-[8px] font-bold px-0.5 rounded"
            style={{ background: "rgba(125,211,252,0.95)", color: "#082F49" }}
            title={`xG ${xg.toFixed(2)}`}
          >{xg.toFixed(2)}</span>
        )}
      </div>
      <div
        className="mt-0.5 text-[10px] font-medium px-1 rounded leading-tight max-w-[88px] truncate text-center"
        style={{ background: "rgba(0,0,0,0.6)", color: "#fff" }}
        title={player.player_name}
      >
        {(player.player_name || "?").split(" ").slice(-1)[0]}
      </div>
    </div>
  );
}

function ratingChip(rating) {
  if (rating == null || typeof rating !== "number") return null;
  const c = rating >= 8 ? "#A3E635" : rating >= 7 ? "#FBBF24" : rating >= 6 ? "#94A3B8" : "#FB7185";
  return (
    <span className="ml-auto text-[10px] font-extrabold px-1.5 py-0.5 rounded tabular-nums" style={{ background: c, color: "#0a0a0a" }}>
      {rating.toFixed(1)}
    </span>
  );
}

function PlayerRow({ p, side = "left" }) {
  const alignClass = side === "right" ? "flex-row-reverse text-right" : "";
  return (
    <li className={`flex items-center gap-2 py-1.5 text-xs ${alignClass}`} data-testid={`bench-row-${p.player_name}`}>
      <span className="w-6 text-center font-bold tabular-nums shrink-0" style={{ color: "var(--cp-text-muted)" }}>
        {p.player_number ?? "—"}
      </span>
      <span className="flex-1 truncate text-cp">{p.player_name}</span>
      {p.position_code && (
        <span className="text-[9px] px-1 rounded uppercase shrink-0" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>
          {p.position_code.slice(0, 3)}
        </span>
      )}
      {ratingChip(p.rating)}
    </li>
  );
}

function Bench({ team, label, side = "left" }) {
  if (!team || team.bench.length === 0) return null;
  // Split bench into "made a sub appearance" (sub_in/sub_out present) vs "unused bench"
  const subs = team.bench.filter((p) => p.sub_in_minute != null || p.sub_out_minute != null || p.minutes_played);
  const unused = team.bench.filter((p) => !(p.sub_in_minute != null || p.sub_out_minute != null || p.minutes_played));
  return (
    <div className="mt-3" data-testid={`bench-${label}`}>
      {subs.length > 0 && (
        <>
          <div className="text-[10px] uppercase tracking-widest mb-2 text-center font-bold text-cp">
            Substitutions
          </div>
          <ul className="space-y-0 divide-y mb-3" style={{ borderColor: "var(--cp-border)" }}>
            {subs.map((p, i) => (
              <li key={`s-${i}`} className={`flex items-center gap-2 py-1.5 text-xs ${side === "right" ? "flex-row-reverse text-right" : ""}`} data-testid={`sub-row-${p.player_name}`}>
                <span className={`shrink-0 inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold`} style={{ background: "rgba(34,197,94,0.18)", color: "#22C55E" }}>
                  ↑
                </span>
                <span className="text-[10px] font-bold tabular-nums shrink-0 w-9" style={{ color: "var(--cp-text-muted)" }}>
                  {p.sub_in_minute != null ? `${p.sub_in_minute}'` : "—"}
                </span>
                <span className="flex-1 truncate text-cp">{p.player_name}</span>
                {ratingChip(p.rating)}
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="text-[10px] uppercase tracking-widest mb-1.5 text-center font-bold text-cp">
        {label} · Bench
      </div>
      <ul className="grid grid-cols-1 divide-y" style={{ borderColor: "var(--cp-border)" }}>
        {(unused.length ? unused : team.bench).map((p, i) => (
          <PlayerRow key={i} p={p} side={side} />
        ))}
      </ul>
    </div>
  );
}

function deriveFormation(team) {
  if (team.formation) return team.formation;
  const rowCounts = {};
  team.starters.forEach((p) => {
    const code = (p.position_code || "").toLowerCase();
    const row = POSITION_ROW[code] || 3;
    if (row > 1) rowCounts[row] = (rowCounts[row] || 0) + 1;
  });
  const rows = Object.keys(rowCounts).map(Number).sort((a, b) => a - b);
  const out = rows.map((r) => rowCounts[r]).join("-");
  return out || null;
}

export default function LineupPitch({ lineups, homeTeamId, awayTeamId, homeName, awayName }) {
  // Track viewport orientation: portrait pitch on mobile, landscape on desktop.
  const [isMobile, setIsMobile] = useState(typeof window !== "undefined" ? window.innerWidth < 768 : false);
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  if (!lineups || lineups.length === 0) {
    return (
      <div className="text-center text-sm p-6" style={{ color: "var(--cp-text-muted)" }} data-testid="lineup-empty">
        Lineups not announced yet — typically posted ~1 hour before kickoff.
      </div>
    );
  }

  // Bucket starters/bench per team
  const buckets = { home: { starters: [], bench: [], formation: null },
                    away: { starters: [], bench: [], formation: null } };
  for (const row of lineups) {
    if (row.team_id === homeTeamId)
      (row.starter ? buckets.home.starters : buckets.home.bench).push(row);
    else if (row.team_id === awayTeamId)
      (row.starter ? buckets.away.starters : buckets.away.bench).push(row);
    if (row.formation && row.team_id === homeTeamId) buckets.home.formation = row.formation;
    if (row.formation && row.team_id === awayTeamId) buckets.away.formation = row.formation;
  }
  const home = buckets.home;
  const away = buckets.away;
  if (home.starters.length === 0 && away.starters.length === 0) {
    return (
      <div className="text-center text-sm p-6" style={{ color: "var(--cp-text-muted)" }} data-testid="lineup-no-starters">
        Starting XIs unavailable.
      </div>
    );
  }

  const homeFormation = deriveFormation(home);
  const awayFormation = deriveFormation(away);
  const homePositions = computePositions(home.starters);
  const awayPositions = computePositions(away.starters);

  const PITCH_BG = "repeating-linear-gradient(90deg, #0e6b3a 0 8%, #0a5a31 8% 16%)";
  const PITCH_BG_VERT = "repeating-linear-gradient(0deg, #0e6b3a 0 8%, #0a5a31 8% 16%)";

  return (
    <div data-testid="lineup-pitch">
      <div className="grid grid-cols-2 text-center text-[11px] uppercase tracking-widest mb-2" style={{ color: "var(--cp-text-muted)" }}>
        <div><span className="font-bold text-cp-lime">{homeName}</span>{homeFormation ? ` · ${homeFormation}` : ""}</div>
        <div><span className="font-bold text-cp-lime">{awayName}</span>{awayFormation ? ` · ${awayFormation}` : ""}</div>
      </div>

      {isMobile ? (
        /* ── Mobile: vertical pitch · home top, away bottom ────────── */
        <div
          className="relative w-full rounded-lg overflow-hidden border mx-auto"
          style={{
            aspectRatio: "3 / 4",
            maxWidth: "min(100%, 520px)",
            background: PITCH_BG_VERT,
            borderColor: "rgba(255,255,255,0.12)",
          }}
        >
          {/* Center line + circle */}
          <div className="absolute left-0 right-0 top-1/2 h-px bg-white/60"/>
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-20 h-20 border border-white/60 rounded-full"/>
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 bg-white rounded-full"/>
          {/* Penalty boxes (top/bottom) */}
          <div className="absolute left-1/2 -translate-x-1/2 top-0 w-[55%] h-[14%] border-b border-x border-white/60"/>
          <div className="absolute left-1/2 -translate-x-1/2 bottom-0 w-[55%] h-[14%] border-t border-x border-white/60"/>
          {/* Goal boxes */}
          <div className="absolute left-1/2 -translate-x-1/2 top-0 w-[28%] h-[6%] border-b border-x border-white/60"/>
          <div className="absolute left-1/2 -translate-x-1/2 bottom-0 w-[28%] h-[6%] border-t border-x border-white/60"/>

          {/* Home (top half) — depth 0 = own goal at TOP (y=4%), 1 = centre (y≈46%) */}
          {homePositions.map(({ player, depth, lane }, i) => {
            const y = depth * 42 + 4;
            const x = lane * 90 + 5;
            return (
              <div key={`H-${i}`} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${x}%`, top: `${y}%` }} data-testid={`player-home-${i}`}>
                <PlayerChip player={player} color="#C6FF3D"/>
              </div>
            );
          })}
          {/* Away (bottom half) — depth 0 = own goal at BOTTOM (y≈96%), 1 = centre (y≈54%) */}
          {awayPositions.map(({ player, depth, lane }, i) => {
            const y = 96 - depth * 42;
            const x = 95 - lane * 90;
            return (
              <div key={`A-${i}`} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${x}%`, top: `${y}%` }} data-testid={`player-away-${i}`}>
                <PlayerChip player={player} color="#FFFFFF"/>
              </div>
            );
          })}
        </div>
      ) : (
        /* ── Desktop: horizontal pitch · home left, away right ─────── */
        <div
          className="relative w-full rounded-lg overflow-hidden border"
          style={{
            aspectRatio: "16 / 10",
            background: PITCH_BG,
            borderColor: "rgba(255,255,255,0.12)",
          }}
        >
          <div className="absolute top-0 bottom-0 left-1/2 w-px bg-white/60"/>
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-24 h-24 border border-white/60 rounded-full"/>
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 bg-white rounded-full"/>
          <div className="absolute top-1/2 -translate-y-1/2 left-0 w-[14%] h-[55%] border-r border-y border-white/60"/>
          <div className="absolute top-1/2 -translate-y-1/2 right-0 w-[14%] h-[55%] border-l border-y border-white/60"/>
          <div className="absolute top-1/2 -translate-y-1/2 left-0 w-[6%] h-[28%] border-r border-y border-white/60"/>
          <div className="absolute top-1/2 -translate-y-1/2 right-0 w-[6%] h-[28%] border-l border-y border-white/60"/>

          {homePositions.map(({ player, depth, lane }, i) => {
            const x = depth * 42 + 4;
            const y = lane * 86 + 7;
            return (
              <div key={`H-${i}`} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${x}%`, top: `${y}%` }} data-testid={`player-home-${i}`}>
                <PlayerChip player={player} color="#C6FF3D"/>
              </div>
            );
          })}
          {awayPositions.map(({ player, depth, lane }, i) => {
            const x = 100 - (depth * 42 + 4);
            const y = lane * 86 + 7;
            return (
              <div key={`A-${i}`} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${x}%`, top: `${y}%` }} data-testid={`player-away-${i}`}>
                <PlayerChip player={player} color="#FFFFFF"/>
              </div>
            );
          })}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
        <Bench team={home} label={homeName || "Home"} side="left"/>
        <Bench team={away} label={awayName || "Away"} side="right"/>
      </div>
    </div>
  );
}
