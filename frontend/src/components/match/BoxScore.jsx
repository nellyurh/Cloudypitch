import React from "react";
import { Trophy } from "lucide-react";

/**
 * Box Score — Basketball / American Football / NBA player stats table.
 *
 * Reads from match.box_score (or match.player_stats / lineups player rows).
 * Falls back to per-period scoreline if no player rows are available.
 */
const BoxScore = ({ match, lineups = [] }) => {
  const home = match.home_team_name, away = match.away_team_name;
  // Per-period scoreline (Q1-Q4 / OT / sets / innings)
  const periods = match.periods || match.linescore || [];
  // Player rows: prefer `box_score` (sportmonks/apisports nba), then `player_stats`,
  // then walk lineups for any rows with stats.
  let playerRows = match.box_score || match.player_stats || [];
  if (!Array.isArray(playerRows) || playerRows.length === 0) {
    playerRows = [];
    for (const team of lineups || []) {
      for (const p of (team.players || team.starting_xi || [])) {
        if (p.points != null || p.minutes != null || p.rebounds != null) {
          playerRows.push({ ...p, team_id: team.team_id, team_name: team.team_name });
        }
      }
    }
  }

  const homeRows = playerRows.filter(p => p.team_id === match.home_team_id || p.team_name === home);
  const awayRows = playerRows.filter(p => p.team_id === match.away_team_id || p.team_name === away);

  return (
    <div className="space-y-4" data-testid="box-score">
      {/* Per-period header */}
      {periods.length > 0 && (
        <div className="cp-surface overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr style={{ color: "var(--cp-text-muted)" }}>
                <th className="text-left p-2">Team</th>
                {periods.map((_, i) => <th key={i} className="text-center">Q{i + 1}</th>)}
                <th className="text-center font-bold text-cp-lime">T</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t" style={{ borderColor: "var(--cp-border)" }}>
                <td className="p-2 font-bold">{home}</td>
                {periods.map((p, i) => <td key={i} className="text-center tabular-nums">{p.home ?? p.home_score ?? "—"}</td>)}
                <td className="text-center tabular-nums font-extrabold text-cp-lime">{match.home_score}</td>
              </tr>
              <tr className="border-t" style={{ borderColor: "var(--cp-border)" }}>
                <td className="p-2 font-bold">{away}</td>
                {periods.map((p, i) => <td key={i} className="text-center tabular-nums">{p.away ?? p.away_score ?? "—"}</td>)}
                <td className="text-center tabular-nums font-extrabold text-cp-lime">{match.away_score}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* Player stats per team */}
      {[{ name: home, rows: homeRows }, { name: away, rows: awayRows }].map((side, idx) => (
        side.rows.length > 0 && (
          <div key={idx} className="cp-surface overflow-hidden">
            <div className="cp-card-header normal-case font-bold">{side.name}</div>
            <table className="w-full text-xs">
              <thead>
                <tr style={{ color: "var(--cp-text-muted)" }}>
                  <th className="text-left p-2">Player</th>
                  <th className="text-center">Min</th><th className="text-center">Pts</th>
                  <th className="text-center">Reb</th><th className="text-center">Ast</th>
                  <th className="text-center">Stl</th><th className="text-center">Blk</th>
                  <th className="text-center">FG</th><th className="text-center">3P</th>
                </tr>
              </thead>
              <tbody>
                {side.rows.slice(0, 15).map((p, i) => (
                  <tr key={p.id || p.player_id || i} className="border-t" style={{ borderColor: "var(--cp-border)" }}>
                    <td className="p-2 truncate">{p.name || p.player_name || "—"}</td>
                    <td className="text-center tabular-nums">{p.minutes ?? p.min ?? "—"}</td>
                    <td className="text-center tabular-nums font-bold">{p.points ?? p.pts ?? "—"}</td>
                    <td className="text-center tabular-nums">{p.rebounds ?? p.reb ?? "—"}</td>
                    <td className="text-center tabular-nums">{p.assists ?? p.ast ?? "—"}</td>
                    <td className="text-center tabular-nums">{p.steals ?? p.stl ?? "—"}</td>
                    <td className="text-center tabular-nums">{p.blocks ?? p.blk ?? "—"}</td>
                    <td className="text-center tabular-nums">{p.fg ?? `${p.fgm ?? 0}/${p.fga ?? 0}`}</td>
                    <td className="text-center tabular-nums">{p.three ?? p.three_pt ?? `${p.tpm ?? 0}/${p.tpa ?? 0}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ))}

      {playerRows.length === 0 && (
        <div className="cp-surface p-6 text-center text-sm" style={{ color: "var(--cp-text-muted)" }} data-testid="box-score-empty">
          <Trophy size={24} className="mx-auto opacity-60 mb-2"/>
          Box score will populate once the game tips off.
        </div>
      )}
    </div>
  );
};

export default BoxScore;
