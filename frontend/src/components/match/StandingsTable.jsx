import React, { useEffect, useState } from "react";
import api from "../../lib/api";

/**
 * Standings tab — full league table, current match's two teams highlighted.
 * Lazy-loads from /api/matches/{id}/standings (which reads db.standings populated
 * by the hourly sportmonks standings sync).
 */
const StandingsTable = ({ matchId }) => {
  const [rows, setRows] = useState(null);
  const [highlight, setHighlight] = useState([]);
  useEffect(() => {
    let mounted = true;
    api.get(`/matches/${matchId}/standings`).then(({ data }) => {
      if (!mounted) return;
      setRows(data.standings || []);
      setHighlight(data.highlight_team_ids || []);
    }).catch(() => mounted && setRows([]));
    return () => { mounted = false; };
  }, [matchId]);
  if (rows === null) return <div className="text-center text-sm py-6" style={{ color: "var(--cp-text-muted)" }}>Loading standings…</div>;
  if (!rows.length) return (
    <div className="text-center text-sm py-6" style={{ color: "var(--cp-text-muted)" }} data-testid="standings-empty">
      Standings not yet ingested for this competition.
    </div>
  );
  return (
    <div className="overflow-x-auto" data-testid="standings-table">
      <table className="w-full text-xs">
        <thead>
          <tr style={{ color: "var(--cp-text-muted)" }}>
            <th className="text-center p-2 w-8">#</th>
            <th className="text-left">Team</th>
            <th className="text-center">P</th>
            <th className="text-center">W</th>
            <th className="text-center">D</th>
            <th className="text-center">L</th>
            <th className="text-center">GF</th>
            <th className="text-center">GA</th>
            <th className="text-center">GD</th>
            <th className="text-center font-bold text-cp-lime">Pts</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const isHighlight = highlight.includes(r.team_id);
            return (
              <tr
                key={r.id || r.team_id}
                className="border-t"
                style={{
                  borderColor: "var(--cp-border)",
                  background: isHighlight ? "rgba(163,230,53,0.08)" : "transparent",
                }}
                data-testid={`standing-row-${r.team_id || r.position}`}
              >
                <td className="text-center p-2 tabular-nums font-bold">{r.position}</td>
                <td className="text-left flex items-center gap-2 p-2">
                  {r.team_logo && <img src={r.team_logo} className="w-4 h-4 object-contain" alt="" onError={(e)=>{e.target.style.display="none"}}/>}
                  <span className={isHighlight ? "text-cp-lime font-extrabold" : ""}>{r.team_name}</span>
                </td>
                <td className="text-center tabular-nums">{r.played ?? "—"}</td>
                <td className="text-center tabular-nums">{r.won ?? "—"}</td>
                <td className="text-center tabular-nums">{r.draw ?? r.draws ?? "—"}</td>
                <td className="text-center tabular-nums">{r.lost ?? "—"}</td>
                <td className="text-center tabular-nums">{r.goals_for ?? "—"}</td>
                <td className="text-center tabular-nums">{r.goals_against ?? "—"}</td>
                <td className="text-center tabular-nums">{(r.goal_difference != null) ? (r.goal_difference > 0 ? `+${r.goal_difference}` : r.goal_difference) : "—"}</td>
                <td className="text-center tabular-nums font-extrabold text-cp-lime">{r.points ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default StandingsTable;
