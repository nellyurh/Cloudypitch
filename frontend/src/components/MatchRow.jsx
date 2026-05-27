import React from "react";
import { Link } from "react-router-dom";

function statusText(m) {
  if (m.is_live) return { text: m.minute ? `${m.minute}'` : (["HT"].includes(m.status) ? "HT" : (m.status_long || "LIVE")), live: true };
  if (["FT", "AET", "PEN"].includes(m.status)) return { text: "FT", live: false };
  if (["HT"].includes(m.status)) return { text: "HT", live: true };
  if (["POSTP"].includes(m.status)) return { text: "PP", live: false };
  if (["CANCL", "ABAN"].includes(m.status)) return { text: "—", live: false };
  try {
    const d = new Date(m.scheduled_at);
    return {
      text: d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }),
      live: false,
    };
  } catch (_) {
    return { text: "—", live: false };
  }
}

const TeamLogo = ({ src, name }) => {
  if (src) return <img src={src} alt="" className="w-[18px] h-[18px] object-contain shrink-0" onError={(e) => { e.target.style.display = "none"; }} />;
  return (
    <span className="inline-flex items-center justify-center w-[18px] h-[18px] rounded-sm text-[9px] font-bold shrink-0" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>
      {(name || "?").slice(0, 1).toUpperCase()}
    </span>
  );
};

export const MatchRow = ({ m, sport = "football" }) => {
  const st = statusText(m);
  const started = !["NS", "TBD", "POSTP", "CANCL", "ABAN"].includes(m.status);
  const finished = ["FT", "AET", "PEN"].includes(m.status);
  const hs = m.home_score ?? 0;
  const as = m.away_score ?? 0;
  const homeWin = (finished || m.is_live) && hs > as;
  const awayWin = (finished || m.is_live) && as > hs;

  const isTennis = sport === "tennis" && Array.isArray(m.sets) && m.sets.length > 0;

  return (
    <Link
      to={`/match/${m.id}`}
      className="cp-match-row hover:bg-white/5"
      style={{ borderBottom: "1px solid var(--cp-border)" }}
      data-testid={`match-row-${m.id}`}
    >
      <div className="cp-time-cell">
        {st.live && <span className="cp-live-dot mb-0.5" />}
        <span className={st.live ? "cp-time-live" : ""} data-testid={`match-time-${m.id}`}>{st.text}</span>
      </div>

      <div className="cp-team-cell home">
        <TeamLogo src={m.home_team_logo} name={m.home_team_name} />
        <span className={`cp-team-name ${homeWin ? "winner" : awayWin ? "loser" : ""}`} data-testid={`home-name-${m.id}`}>
          {m.home_team_name || m.home_short || "Home"}
        </span>
        {isTennis && (
          <span className="ml-auto flex items-center gap-1.5 tabular-nums">
            {m.sets.map((s, i) => {
              const win = (s.home_score || 0) > (s.away_score || 0);
              return (
                <span key={i} className="text-[12px] font-mono" style={{ color: win ? "var(--cp-text)" : "var(--cp-text-muted)", fontWeight: win ? 700 : 500 }}>
                  {s.home_score ?? 0}
                  {s.home_tiebreak != null && <sup className="cp-tiebreak">{s.home_tiebreak}</sup>}
                </span>
              );
            })}
          </span>
        )}
      </div>

      <div className="cp-team-cell away">
        <TeamLogo src={m.away_team_logo} name={m.away_team_name} />
        <span className={`cp-team-name ${awayWin ? "winner" : homeWin ? "loser" : ""}`} data-testid={`away-name-${m.id}`}>
          {m.away_team_name || m.away_short || "Away"}
        </span>
        {isTennis && (
          <span className="ml-auto flex items-center gap-1.5 tabular-nums">
            {m.sets.map((s, i) => {
              const win = (s.away_score || 0) > (s.home_score || 0);
              return (
                <span key={i} className="text-[12px] font-mono" style={{ color: win ? "var(--cp-text)" : "var(--cp-text-muted)", fontWeight: win ? 700 : 500 }}>
                  {s.away_score ?? 0}
                  {s.away_tiebreak != null && <sup className="cp-tiebreak">{s.away_tiebreak}</sup>}
                </span>
              );
            })}
          </span>
        )}
      </div>

      {!isTennis && started && (
        <>
          <span className={`cp-score-cell home ${homeWin ? "winner" : awayWin ? "loser" : ""}`} data-testid={`home-score-${m.id}`}>{hs}</span>
          <span className={`cp-score-cell away ${awayWin ? "winner" : homeWin ? "loser" : ""}`} data-testid={`away-score-${m.id}`}>{as}</span>
        </>
      )}
    </Link>
  );
};

export default MatchRow;
