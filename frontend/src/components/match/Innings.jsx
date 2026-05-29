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
      {match.result_text && (
        <div className="cp-surface p-3 text-center text-sm font-extrabold text-cp-lime" data-testid="cricket-result">
          {match.result_text}
        </div>
      )}
      {(match.venue_name || match.match_format) && (
        <div className="text-[10px] uppercase tracking-widest text-center" style={{ color: "var(--cp-text-muted)" }}>
          {match.match_format && <span className="mr-2">{match.match_format}</span>}
          {match.venue_name}
        </div>
      )}
      {innings.map((inn, i) => (
        <div key={i} className="cp-surface overflow-hidden">
          <div className="cp-card-header normal-case flex items-center justify-between">
            <span className="font-bold">{inn.team_name || (i % 2 === 0 ? match.home_team_name : match.away_team_name)} · Innings {inn.innings_no || Math.floor(i / 2) + 1}</span>
            <span className="text-cp-lime font-extrabold tabular-nums">
              {inn.runs ?? "—"}{inn.wickets != null ? `/${inn.wickets}` : ""}
              {inn.overs ? <span className="ml-1 text-[10px] opacity-70">({inn.overs} ov)</span> : null}
            </span>
          </div>
          {Array.isArray(inn.top_batters) && inn.top_batters.length > 0 && (
            <div className="px-3 py-2 text-xs border-t" style={{ borderColor: "var(--cp-border)" }}>
              <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--cp-text-muted)" }}>Top batters</div>
              {inn.top_batters.slice(0, 4).map((b, j) => (
                <div key={j} className="flex justify-between py-0.5">
                  <span>
                    {b.name}
                    {b.not_out && <span className="ml-1 text-cp-lime">*</span>}
                  </span>
                  <span className="tabular-nums text-right">
                    <b>{b.runs}</b>
                    <span className="opacity-60"> ({b.balls})</span>
                    {(b.fours > 0 || b.sixes > 0) && (
                      <span className="ml-2 opacity-60">{b.fours}×4 · {b.sixes}×6</span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          )}
          {Array.isArray(inn.top_bowlers) && inn.top_bowlers.length > 0 && (
            <div className="px-3 py-2 text-xs border-t" style={{ borderColor: "var(--cp-border)" }}>
              <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--cp-text-muted)" }}>Top bowlers</div>
              {inn.top_bowlers.slice(0, 3).map((b, j) => (
                <div key={j} className="flex justify-between py-0.5">
                  <span>{b.name}</span>
                  <span className="tabular-nums text-right">
                    <b>{b.wickets}/{b.runs}</b>
                    <span className="opacity-60"> ({b.overs} ov{b.maidens ? `, ${b.maidens}m` : ""})</span>
                  </span>
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
