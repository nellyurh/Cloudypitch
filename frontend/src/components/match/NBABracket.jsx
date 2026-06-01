import React, { useEffect, useState } from "react";
import api from "../../lib/api";
import { Trophy } from "lucide-react";

/**
 * NBA Playoffs / Bracket view. Renders 4 columns (First Round, Conf Semis, Conf Finals, Finals).
 * Each cell shows the series matchup with wins (best-of-7).
 */
const NBABracket = () => {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/nba/playoffs");
        setData(data);
      } catch (e) {
        setErr("Failed to load playoffs.");
      }
    })();
  }, []);

  if (err) return <div className="text-sm text-red-400" data-testid="nba-bracket-error">{err}</div>;
  if (!data) return <div className="text-sm" style={{ color: "var(--cp-text-muted)" }} data-testid="nba-bracket-loading">Loading bracket…</div>;
  if ((data.total_series || 0) === 0) {
    return (
      <div className="cp-surface p-6 text-center text-sm" style={{ color: "var(--cp-text-muted)" }} data-testid="nba-bracket-empty">
        <Trophy size={24} className="mx-auto opacity-60 mb-2"/>
        Playoffs bracket will populate when post-season games are scheduled.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="nba-bracket">
      <div className="grid grid-cols-4 gap-3 min-w-[760px]">
        {(data.rounds || []).map(rnd => (
          <div key={rnd.name} className="space-y-3">
            <div className="text-[10px] uppercase tracking-widest text-center font-bold" style={{ color: "var(--cp-text-muted)" }}>
              {rnd.name}
            </div>
            <div className="space-y-2 flex flex-col" style={{ justifyContent: rnd.name === "Finals" ? "center" : "flex-start", minHeight: "100%" }}>
              {(rnd.series || []).map((s, i) => (
                <SeriesCard key={i} s={s}/>
              ))}
              {(rnd.series || []).length === 0 && (
                <div className="rounded p-3 text-[11px] text-center opacity-50" style={{ background: "var(--cp-surface-2)" }}>
                  TBD
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

function SeriesCard({ s }) {
  const homeWon = s.winner_team_id === s.home_team_id;
  const awayWon = s.winner_team_id === s.away_team_id;
  return (
    <div className="rounded overflow-hidden" style={{ background: "var(--cp-surface-2)", border: "1px solid var(--cp-border)" }} data-testid={`nba-series-${s.home_team_id}-${s.away_team_id}`}>
      <SeriesRow name={s.home_team_name} logo={s.home_team_logo} wins={s.home_wins} won={homeWon} eliminated={awayWon}/>
      <SeriesRow name={s.away_team_name} logo={s.away_team_logo} wins={s.away_wins} won={awayWon} eliminated={homeWon}/>
    </div>
  );
}

function SeriesRow({ name, logo, wins, won, eliminated }) {
  return (
    <div className={`flex items-center gap-2 px-2 py-1.5 text-xs ${won ? "bg-cp-lime/10" : ""} ${eliminated ? "opacity-50" : ""}`} style={{ borderTop: "1px solid var(--cp-border)" }}>
      {logo ? (
        <img src={logo} alt="" className="w-5 h-5 object-contain"/>
      ) : (
        <div className="w-5 h-5 rounded-full" style={{ background: "var(--cp-surface)" }}/>
      )}
      <span className={`flex-1 truncate ${won ? "font-extrabold text-cp-lime" : "font-medium"}`}>{name}</span>
      <span className={`tabular-nums w-5 text-right ${won ? "text-cp-lime font-extrabold" : ""}`}>{wins}</span>
    </div>
  );
}

export default NBABracket;
