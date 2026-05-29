import React from "react";

const POSITION_ROW = {
  goalkeeper: 1,
  defender: 2,
  midfielder: 3,
  attacker: 4,
  forward: 4,
};

/**
 * Compute pitch positions for one team's starters.
 * Uses position_code → row, grid (1-11 slot) → column ordering within row.
 * Returns array of {player, x, y} percentages within the team's half.
 */
function computePositions(starters, mirror) {
  if (!starters || starters.length === 0) return [];

  // Group by row
  const rows = {};
  starters.forEach((p) => {
    const code = (p.position_code || "").toLowerCase();
    const row = POSITION_ROW[code] || 3;
    if (!rows[row]) rows[row] = [];
    rows[row].push(p);
  });

  // Sort each row by grid (or jersey as fallback) for stable left-right placement
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

  const positions = [];
  rowKeys.forEach((row) => {
    const rowPlayers = rows[row];
    const n = rowPlayers.length;
    // X depth (own goal side → centre line): row 1 = closest to goal (x≈3%), max row = closest to centre (~48%)
    const denom = Math.max(1, maxRow - minRow);
    const xPct = ((row - minRow) / denom) * 42 + 4;
    rowPlayers.forEach((p, i) => {
      const yPct = ((i + 0.5) / n) * 86 + 7;
      positions.push({ player: p, x: mirror ? 100 - xPct : xPct, y: yPct });
    });
  });
  return positions;
}

function TeamHalf({ team, mirror, color, label }) {
  if (!team || team.starters.length === 0) return null;
  const positions = computePositions(team.starters, mirror);
  return (
    <>
      {positions.map(({ player, x, y }, i) => {
        const rating = typeof player.rating === "number" ? player.rating : null;
        const xg = typeof player.xg === "number" && player.xg > 0 ? player.xg : null;
        const ratingColor = rating == null ? null : rating >= 8 ? "#A3E635" : rating >= 7 ? "#FBBF24" : rating >= 6 ? "#94A3B8" : "#FB7185";
        return (
          <div
            key={`${player.player_name}-${i}`}
            className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center"
            style={{ left: `${x}%`, top: `${y}%` }}
            data-testid={`player-${label}-${i}`}
          >
            <div className="relative">
              <div
                className="w-8 h-8 md:w-9 md:h-9 rounded-full flex items-center justify-center text-[11px] font-extrabold tabular-nums shadow-md ring-2 ring-black/40"
                style={{ background: color, color: "#0a0a0a" }}
              >
                {player.player_number ?? "?"}
              </div>
              {rating != null && (
                <span
                  className="absolute -top-1 -right-1 text-[8px] font-extrabold px-1 rounded shadow"
                  style={{ background: ratingColor, color: "#0a0a0a" }}
                  data-testid={`rating-${player.player_name}`}
                >{rating.toFixed(1)}</span>
              )}
              {xg != null && (
                <span
                  className="absolute -bottom-1 -left-1 text-[8px] font-bold px-0.5 rounded"
                  style={{ background: "rgba(125,211,252,0.95)", color: "#082F49" }}
                  data-testid={`xg-${player.player_name}`}
                  title={`xG ${xg.toFixed(2)}`}
                >{xg.toFixed(2)}</span>
              )}
            </div>
            <div
              className="mt-0.5 text-[10px] font-medium px-1 rounded leading-tight max-w-[80px] truncate text-center"
              style={{ background: "rgba(0,0,0,0.55)", color: "#fff" }}
              title={player.player_name}
            >
              {(player.player_name || "?").split(" ").slice(-1)[0]}
            </div>
          </div>
        );
      })}
    </>
  );
}

function Bench({ team, label }) {
  if (!team || team.bench.length === 0) return null;
  return (
    <div className="mt-2" data-testid={`bench-${label}`}>
      <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--cp-text-muted)" }}>
        {label} Bench
      </div>
      <ul className="grid grid-cols-2 md:grid-cols-3 gap-x-3 gap-y-0.5 text-xs">
        {team.bench.map((p, i) => (
          <li key={i} className="flex items-center gap-2 truncate">
            <span className="w-5 text-center font-bold tabular-nums" style={{ color: "var(--cp-text-muted)" }}>
              {p.player_number ?? "—"}
            </span>
            <span className="truncate">{p.player_name}</span>
            {p.position_code && (
              <span className="text-[9px] px-1 rounded uppercase" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>
                {p.position_code.slice(0, 3)}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function LineupPitch({ lineups, homeTeamId, awayTeamId, homeName, awayName }) {
  if (!lineups || lineups.length === 0) {
    return <div className="text-sm" style={{ color: "var(--cp-text-muted)" }}>No lineups yet.</div>;
  }

  const splitTeam = (teamId) => {
    const players = lineups.filter((l) => l.team_id === teamId);
    const formation = players.find((p) => p.formation)?.formation || null;
    return {
      formation,
      starters: players.filter((p) => p.starter),
      bench: players.filter((p) => !p.starter),
    };
  };

  let home = splitTeam(homeTeamId);
  let away = splitTeam(awayTeamId);

  // Fallback: if team_id matching produced nothing, partition by first/second unique team_id
  if (home.starters.length === 0 && away.starters.length === 0) {
    const ids = [...new Set(lineups.map((l) => l.team_id).filter(Boolean))];
    if (ids.length >= 2) {
      home = splitTeam(ids[0]);
      away = splitTeam(ids[1]);
    }
  }

  // Derive formation from row counts if not provided
  const deriveFormation = (team) => {
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
  };
  const homeFormation = deriveFormation(home);
  const awayFormation = deriveFormation(away);

  return (
    <div data-testid="lineup-pitch">
      <div className="grid grid-cols-2 text-center text-[11px] uppercase tracking-widest mb-2" style={{ color: "var(--cp-text-muted)" }}>
        <div><span className="font-bold text-cp-lime">{homeName}</span>{homeFormation ? ` · ${homeFormation}` : ""}</div>
        <div><span className="font-bold text-cp-lime">{awayName}</span>{awayFormation ? ` · ${awayFormation}` : ""}</div>
      </div>

      <div
        className="relative w-full rounded-lg overflow-hidden border"
        style={{
          aspectRatio: "16 / 10",
          background:
            "repeating-linear-gradient(90deg, #0e6b3a 0 8%, #0a5a31 8% 16%)",
          borderColor: "rgba(255,255,255,0.12)",
        }}
      >
        {/* Center line + circle */}
        <div className="absolute top-0 bottom-0 left-1/2 w-px bg-white/60" />
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 md:w-24 md:h-24 border border-white/60 rounded-full" />
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 bg-white rounded-full" />
        {/* Penalty boxes */}
        <div className="absolute top-1/2 -translate-y-1/2 left-0 w-[14%] h-[55%] border-r border-y border-white/60" />
        <div className="absolute top-1/2 -translate-y-1/2 right-0 w-[14%] h-[55%] border-l border-y border-white/60" />
        {/* Goal boxes */}
        <div className="absolute top-1/2 -translate-y-1/2 left-0 w-[6%] h-[28%] border-r border-y border-white/60" />
        <div className="absolute top-1/2 -translate-y-1/2 right-0 w-[6%] h-[28%] border-l border-y border-white/60" />
        {/* Goals */}
        <div className="absolute top-1/2 -translate-y-1/2 -left-1 w-1 h-[12%] bg-white" />
        <div className="absolute top-1/2 -translate-y-1/2 -right-1 w-1 h-[12%] bg-white" />

        <TeamHalf team={home} mirror={false} color="#C6FF3D" label="home" />
        <TeamHalf team={away} mirror={true} color="#FFFFFF" label="away" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
        <Bench team={home} label={homeName || "Home"} />
        <Bench team={away} label={awayName || "Away"} />
      </div>
    </div>
  );
}
