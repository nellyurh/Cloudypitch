import React from "react";
import { Link } from "react-router-dom";
import { Star } from "lucide-react";

// Format match time/status cell
function statusText(m) {
  if (m.is_live) return { text: m.minute ? `${m.minute}'` : (m.status_long || "LIVE"), live: true };
  if (["FT", "AET", "PEN"].includes(m.status)) return { text: "FT", live: false };
  if (["HT"].includes(m.status)) return { text: "HT", live: true };
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

const TeamLogo = ({ team, name }) => {
  if (team) {
    return <img src={team} alt="" className="w-5 h-5 object-contain rounded-sm" onError={(e) => { e.target.style.display = "none"; }} />;
  }
  return (
    <span className="inline-flex items-center justify-center w-5 h-5 rounded-sm text-[10px] font-bold" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>
      {(name || "?").slice(0, 1).toUpperCase()}
    </span>
  );
};

export const MatchRow = ({ m, sport = "football" }) => {
  const st = statusText(m);
  const finished = ["FT", "AET", "PEN"].includes(m.status);
  const hs = m.home_score ?? 0;
  const as = m.away_score ?? 0;
  const homeWin = (finished || m.is_live) && hs > as;
  const awayWin = (finished || m.is_live) && as > hs;

  const isTennis = sport === "tennis" && Array.isArray(m.sets);

  return (
    <Link
      to={`/match/${m.id}`}
      className="cp-match-row block hover:bg-white/5"
      style={{ borderBottom: "1px solid var(--cp-border)" }}
      data-testid={`match-row-${m.id}`}
    >
      <div className="cp-time-cell">
        {st.live && <span className="cp-live-dot mb-1" />}
        <span className={st.live ? "cp-time-live" : ""} data-testid={`match-time-${m.id}`}>{st.text}</span>
      </div>

      <div className="min-w-0">
        {/* HOME ROW */}
        <div className="cp-team-cell" style={{ borderBottom: "1px dashed var(--cp-border)" }}>
          <TeamLogo team={m.home_team_logo} name={m.home_team_name} />
          <span className={`cp-team-name ${homeWin ? "winner" : finished ? "loser" : ""}`} data-testid={`home-name-${m.id}`}>
            {m.home_team_name || m.home_short || "Home"}
          </span>
          {isTennis && (
            <span className="ml-auto flex items-center gap-1.5 tabular-nums">
              {m.sets.map((s, i) => (
                <span key={i} className="text-xs font-mono" style={{ color: (s.home_score || 0) > (s.away_score || 0) ? "#A3E635" : "var(--cp-text-muted)" }}>
                  {s.home_score ?? 0}
                  {s.home_tiebreak != null && <sup className="cp-tiebreak">{s.home_tiebreak}</sup>}
                </span>
              ))}
            </span>
          )}
        </div>
        {/* AWAY ROW */}
        <div className="cp-team-cell">
          <TeamLogo team={m.away_team_logo} name={m.away_team_name} />
          <span className={`cp-team-name ${awayWin ? "winner" : finished ? "loser" : ""}`} data-testid={`away-name-${m.id}`}>
            {m.away_team_name || m.away_short || "Away"}
          </span>
          {isTennis && (
            <span className="ml-auto flex items-center gap-1.5 tabular-nums">
              {m.sets.map((s, i) => (
                <span key={i} className="text-xs font-mono" style={{ color: (s.away_score || 0) > (s.home_score || 0) ? "#A3E635" : "var(--cp-text-muted)" }}>
                  {s.away_score ?? 0}
                  {s.away_tiebreak != null && <sup className="cp-tiebreak">{s.away_tiebreak}</sup>}
                </span>
              ))}
            </span>
          )}
        </div>
      </div>

      {!isTennis && (
        <div className="text-right pr-2 flex flex-col items-end justify-center" style={{ minHeight: 56 }}>
          <span className={`cp-score ${homeWin ? "winner" : finished ? "loser" : ""}`} data-testid={`home-score-${m.id}`}>
            {(m.status === "NS" || m.status === "TBD") ? "" : hs}
          </span>
          <span className={`cp-score ${awayWin ? "winner" : finished ? "loser" : ""}`} data-testid={`away-score-${m.id}`}>
            {(m.status === "NS" || m.status === "TBD") ? "" : as}
          </span>
        </div>
      )}
    </Link>
  );
};

export default MatchRow;
