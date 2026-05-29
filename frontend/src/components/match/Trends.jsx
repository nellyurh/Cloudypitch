import React from "react";
import { TrendingUp, Users, Shield } from "lucide-react";

/**
 * Trends / MatchFacts tab.
 *
 * Sportmonks returns up to 759 matchfacts per fixture; ~176 have natural_language
 * sentences (e.g. "Saint-Étienne won their last 5 home games in Ligue 1"). We
 * categorise them by `participant` (home / away / both) and surface up to 30 of
 * the most readable insights.
 */
const Trends = ({ facts = [], homeTeamName, awayTeamName, homeTeamId, awayTeamId }) => {
  if (!Array.isArray(facts) || facts.length === 0) {
    return (
      <div className="text-center text-sm py-6" style={{ color: "var(--cp-text-muted)" }} data-testid="trends-empty">
        <TrendingUp size={24} className="mx-auto opacity-60 mb-2"/>
        Pre-match trends and head-to-head facts arrive a few hours before kickoff.
      </div>
    );
  }
  const home = facts.filter(f => (f.participant || "").toLowerCase() === "home" || (f.basis || "").toLowerCase() === "home").slice(0, 10);
  const away = facts.filter(f => (f.participant || "").toLowerCase() === "away" || (f.basis || "").toLowerCase() === "away").slice(0, 10);
  const h2h  = facts.filter(f => (f.basis || "").toLowerCase() === "h2h" || (f.participant || "").toLowerCase() === "both").slice(0, 10);
  const Section = ({ icon: Icon, title, rows, accent }) => rows.length === 0 ? null : (
    <div className="cp-surface overflow-hidden">
      <div className="cp-card-header normal-case font-bold flex items-center gap-2" style={{ color: accent }}>
        <Icon size={14}/> {title}
      </div>
      <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
        {rows.map((f, i) => (
          <li key={i} className="px-3 py-2 text-xs flex items-start gap-2" data-testid={`trend-${title.toLowerCase().replace(/\s+/g, '-')}-${i}`}>
            <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ background: accent }}/>
            <span className="flex-1 leading-snug">{f.text}</span>
            {f.category && (
              <span className="cp-pill text-[9px] uppercase shrink-0" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>{f.category}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
  return (
    <div className="space-y-3" data-testid="trends-list">
      <Section icon={Shield} title={homeTeamName || "Home"} rows={home} accent="#A3E635"/>
      <Section icon={Shield} title={awayTeamName || "Away"} rows={away} accent="#7DD3FC"/>
      <Section icon={Users} title="Head to Head" rows={h2h} accent="#FBBF24"/>
    </div>
  );
};

export default Trends;
