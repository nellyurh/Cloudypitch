import React from "react";
import { Activity } from "lucide-react";

/**
 * Sets view — tennis / volleyball / table-tennis / badminton.
 * Reads match.sets[] or match.periods[] (both shapes supported).
 */
const Sets = ({ match }) => {
  const sets = match.sets || match.periods || [];
  if (!Array.isArray(sets) || sets.length === 0) {
    return (
      <div className="cp-surface p-6 text-center text-sm" style={{ color: "var(--cp-text-muted)" }} data-testid="sets-empty">
        <Activity size={24} className="mx-auto opacity-60 mb-2"/>
        Set-by-set breakdown will appear once play begins.
      </div>
    );
  }
  return (
    <div className="cp-surface overflow-hidden" data-testid="sets-table">
      <table className="w-full text-sm">
        <thead>
          <tr style={{ color: "var(--cp-text-muted)" }} className="text-xs">
            <th className="text-left p-2">Player / Team</th>
            {sets.map((_, i) => <th key={i} className="text-center px-2">Set {i + 1}</th>)}
            <th className="text-center font-bold text-cp-lime">Match</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t" style={{ borderColor: "var(--cp-border)" }}>
            <td className="p-2 font-bold">{match.home_team_name}</td>
            {sets.map((s, i) => (
              <td key={i} className="text-center px-2 tabular-nums">
                {s.home ?? s.home_score ?? "—"}
                {s.home_tiebreak != null && <sup className="cp-tiebreak">{s.home_tiebreak}</sup>}
              </td>
            ))}
            <td className="text-center tabular-nums font-extrabold text-cp-lime">{match.home_score}</td>
          </tr>
          <tr className="border-t" style={{ borderColor: "var(--cp-border)" }}>
            <td className="p-2 font-bold">{match.away_team_name}</td>
            {sets.map((s, i) => (
              <td key={i} className="text-center px-2 tabular-nums">
                {s.away ?? s.away_score ?? "—"}
                {s.away_tiebreak != null && <sup className="cp-tiebreak">{s.away_tiebreak}</sup>}
              </td>
            ))}
            <td className="text-center tabular-nums font-extrabold text-cp-lime">{match.away_score}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default Sets;
