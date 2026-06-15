import React, { useMemo } from "react";

/**
 * Sofascore-style H2H tab.
 * Layout:
 *  - Aggregate header strip (3 colored wins/draws/losses badges)
 *  - 2-column on desktop: Head-to-head matches (left) · Matches sidebar (right)
 *  - Below: Streaks section (per-row tags computed from h2h aggregates)
 */
export default function H2HCard({ h2h, homeTeamId, awayTeamId, homeName, awayName }) {
  const { wins, draws, losses } = useMemo(() => {
    let w = 0, d = 0, l = 0;
    for (const p of h2h || []) {
      const hs = Number(p.home_score ?? 0);
      const as = Number(p.away_score ?? 0);
      const homeIsHere = p.home_team_id === homeTeamId;
      if (hs === as) { d += 1; continue; }
      const homeWonRow = hs > as;
      const ourWin = (homeIsHere && homeWonRow) || (!homeIsHere && !homeWonRow);
      if (ourWin) w += 1; else l += 1;
    }
    return { wins: w, draws: d, losses: l };
  }, [h2h, homeTeamId]);

  if (!h2h || h2h.length === 0) {
    return (
      <div className="text-center text-sm py-6" style={{ color: "var(--cp-text-muted)" }} data-testid="h2h-empty">
        No prior head-to-head found.
      </div>
    );
  }

  const homeWins = h2h.filter(p => {
    const hs = Number(p.home_score ?? 0), as = Number(p.away_score ?? 0);
    return p.home_team_id === homeTeamId ? hs > as : as > hs;
  }).length;
  const awayWins = h2h.filter(p => {
    const hs = Number(p.home_score ?? 0), as = Number(p.away_score ?? 0);
    return p.home_team_id === awayTeamId ? hs > as : as > hs;
  }).length;

  const totalGoalsHome = h2h.reduce((s, p) => s + (p.home_team_id === homeTeamId ? Number(p.home_score || 0) : Number(p.away_score || 0)), 0);
  const totalGoalsAway = h2h.reduce((s, p) => s + (p.home_team_id === awayTeamId ? Number(p.home_score || 0) : Number(p.away_score || 0)), 0);
  const bothScored = h2h.filter(p => Number(p.home_score || 0) > 0 && Number(p.away_score || 0) > 0).length;
  const over25 = h2h.filter(p => Number(p.home_score || 0) + Number(p.away_score || 0) > 2.5).length;

  return (
    <div data-testid="h2h-card">
      {/* Aggregate strip */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <Badge label={`${homeName} wins`} value={homeWins} tone="home" testId="h2h-home-wins" />
        <Badge label="Draws" value={draws} tone="draw" testId="h2h-draws" />
        <Badge label={`${awayName} wins`} value={awayWins} tone="away" testId="h2h-away-wins" />
      </div>

      {/* 2-column: matches list + summary panel */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* LEFT: Head-to-head matches */}
        <section className="cp-surface !bg-transparent ring-1 ring-white/5 rounded-lg p-3" data-testid="h2h-matches">
          <h4 className="text-center text-[13px] font-bold mb-3 pb-2 border-b" style={{ borderColor: "var(--cp-border)" }}>
            Head-to-head
          </h4>
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {h2h.map((p) => {
              const hs = Number(p.home_score ?? 0);
              const as = Number(p.away_score ?? 0);
              const homeIsOurTeam = p.home_team_id === homeTeamId;
              let outcome;
              if (hs === as) outcome = "D";
              else outcome = (homeIsOurTeam ? hs > as : as > hs) ? "W" : "L";
              const date = p.scheduled_at ? new Date(p.scheduled_at) : null;
              return (
                <li key={p.id} className="flex items-center gap-2 py-2 text-[12px]" data-testid={`h2h-row-${p.id}`}>
                  <span className="text-[10px] tabular-nums w-14 shrink-0" style={{ color: "var(--cp-text-muted)" }}>
                    {date ? date.toLocaleDateString([], { day: "2-digit", month: "short", year: "2-digit" }) : "—"}
                  </span>
                  <span className="flex-1 truncate text-slate-200">
                    <span className={p.home_team_id === homeTeamId ? "font-semibold" : ""}>{p.home_team_name}</span>
                    <b className="mx-1.5 tabular-nums text-slate-100">{hs}-{as}</b>
                    <span className={p.away_team_id === homeTeamId ? "font-semibold" : ""}>{p.away_team_name}</span>
                  </span>
                  <OutcomePill outcome={outcome} />
                </li>
              );
            })}
          </ul>
        </section>

        {/* RIGHT: Summary */}
        <section className="cp-surface !bg-transparent ring-1 ring-white/5 rounded-lg p-3" data-testid="h2h-summary">
          <h4 className="text-center text-[13px] font-bold mb-3 pb-2 border-b" style={{ borderColor: "var(--cp-border)" }}>
            Streaks &amp; trends
          </h4>
          <div className="space-y-2">
            <Streak label="Total meetings" value={h2h.length} />
            <Streak label={`Goals · ${homeName}`} value={totalGoalsHome} accent="home" />
            <Streak label={`Goals · ${awayName}`} value={totalGoalsAway} accent="away" />
            <Streak label="Both teams scored" value={`${bothScored} / ${h2h.length}`} />
            <Streak label="Over 2.5 goals" value={`${over25} / ${h2h.length}`} />
          </div>
        </section>
      </div>
    </div>
  );
}

function Badge({ label, value, tone, testId }) {
  const tones = {
    home: { bg: "rgba(163,230,53,0.12)", border: "rgba(163,230,53,0.35)", fg: "#A3E635" },
    draw: { bg: "rgba(148,163,184,0.12)", border: "rgba(148,163,184,0.3)", fg: "#94A3B8" },
    away: { bg: "rgba(125,211,252,0.12)", border: "rgba(125,211,252,0.35)", fg: "#7DD3FC" },
  };
  const c = tones[tone] || tones.draw;
  return (
    <div
      className="flex flex-col items-center justify-center rounded-lg py-2.5 border"
      style={{ background: c.bg, borderColor: c.border }}
      data-testid={testId}
    >
      <div className="text-2xl font-extrabold tabular-nums leading-none" style={{ color: c.fg }}>{value}</div>
      <div className="text-[10px] uppercase tracking-wider mt-1 text-center px-1 truncate max-w-full" style={{ color: c.fg, opacity: 0.85 }}>{label}</div>
    </div>
  );
}

function OutcomePill({ outcome }) {
  const map = {
    W: { bg: "rgba(34,197,94,0.18)",  fg: "#22C55E" },
    D: { bg: "rgba(148,163,184,0.18)", fg: "#CBD5E1" },
    L: { bg: "rgba(239,68,68,0.18)",  fg: "#EF4444" },
  };
  const c = map[outcome];
  return (
    <span
      className="w-6 h-6 rounded-md text-[11px] font-extrabold inline-flex items-center justify-center shrink-0"
      style={{ background: c.bg, color: c.fg }}
    >
      {outcome}
    </span>
  );
}

function Streak({ label, value, accent }) {
  const accentColor = accent === "home" ? "#A3E635" : accent === "away" ? "#7DD3FC" : "#F8FAFC";
  return (
    <div className="flex items-center justify-between py-1.5 border-b text-[12px]" style={{ borderColor: "var(--cp-border)" }}>
      <span className="text-slate-300">{label}</span>
      <span className="font-bold tabular-nums" style={{ color: accentColor }}>{value}</span>
    </div>
  );
}
