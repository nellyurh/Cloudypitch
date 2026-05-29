import React from "react";
import { Target } from "lucide-react";

/**
 * Innings view — cricket. Each team has 1–2 innings.
 * Looks for match.innings[] or pulls from raw_data fallbacks.
 */
const Innings = ({ match }) => {
  const innings = match.innings || [];
  if (!Array.isArray(innings) || innings.length === 0) {
    return (
      <div className="cp-surface p-6 text-center text-sm" style={{ color: "var(--cp-text-muted)" }} data-testid="innings-empty">
        <Target size={24} className="mx-auto opacity-60 mb-2"/>
        Innings breakdown appears once the toss is decided.
      </div>
    );
  }
  return (
    <div className="space-y-3" data-testid="innings-list">
      {innings.map((inn, i) => (
        <div key={i} className="cp-surface overflow-hidden">
          <div className="cp-card-header normal-case flex items-center justify-between">
            <span className="font-bold">{inn.team_name || (i % 2 === 0 ? match.home_team_name : match.away_team_name)} · Innings {Math.floor(i / 2) + 1}</span>
            <span className="text-cp-lime font-extrabold tabular-nums">
              {inn.runs ?? "—"}/{inn.wickets ?? "—"}
              <span className="ml-1 text-[10px] opacity-70">({inn.overs ?? "—"} ov)</span>
            </span>
          </div>
          {Array.isArray(inn.top_batters) && inn.top_batters.length > 0 && (
            <div className="px-3 py-2 text-xs">
              <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--cp-text-muted)" }}>Top batters</div>
              {inn.top_batters.slice(0, 4).map((b, j) => (
                <div key={j} className="flex justify-between py-0.5">
                  <span>{b.name}</span>
                  <span className="tabular-nums">{b.runs} ({b.balls})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default Innings;
