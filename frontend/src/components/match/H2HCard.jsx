import React, { useMemo, useEffect, useState } from "react";
import api from "../../lib/api";

/**
 * Sofascore-style H2H tab.
 *
 * Layout:
 *  - Top: small scoreline header showing aggregate wins (homeName / "0" / awayName).
 *  - 2-column on desktop:
 *      LEFT  → "Head-to-head" list (the actual h2h matches).
 *              When empty, swapped for a friendly empty state.
 *      RIGHT → "Matches" sidebar — recent + upcoming matches for both teams,
 *              fetched live via /api/teams/{id} (uses Sofascore-style team flag tabs).
 *  - Below: Streaks card + Goal-distribution-by-15-min histogram.
 */
export default function H2HCard({ h2h, homeTeamId, awayTeamId, homeName, awayName }) {
  const [matchesTeam, setMatchesTeam] = useState("home"); // "home" | "away"
  const [homeTeamData, setHomeTeamData] = useState(null);
  const [awayTeamData, setAwayTeamData] = useState(null);

  useEffect(() => {
    if (homeTeamId) {
      api.get(`/teams/${homeTeamId}`).then(({ data }) => setHomeTeamData(data)).catch(() => {});
    }
    if (awayTeamId) {
      api.get(`/teams/${awayTeamId}`).then(({ data }) => setAwayTeamData(data)).catch(() => {});
    }
  }, [homeTeamId, awayTeamId]);

  const { homeWins, draws, awayWins, totalGoalsHome, totalGoalsAway, bothScored, over25, goalsByBucket } = useMemo(() => {
    const list = h2h || [];
    let hw = 0, d = 0, aw = 0, tgh = 0, tga = 0, bs = 0, o25 = 0;
    // 6 buckets: 0-15, 16-30, 31-45, 46-60, 61-75, 76-90
    const buckets = { home_scored: [0,0,0,0,0,0], home_conceded: [0,0,0,0,0,0], away_scored: [0,0,0,0,0,0], away_conceded: [0,0,0,0,0,0] };
    const bucketFor = (m) => Math.min(5, Math.max(0, Math.floor((Number(m) || 0) / 15)));

    for (const p of list) {
      const hs = Number(p.home_score ?? 0);
      const as = Number(p.away_score ?? 0);
      const homeIsHere = p.home_team_id === homeTeamId;
      if (hs === as) d += 1;
      else {
        const homeWonRow = hs > as;
        const ourWin = (homeIsHere && homeWonRow) || (!homeIsHere && !homeWonRow);
        if (ourWin) hw += 1; else aw += 1;
      }
      tgh += homeIsHere ? hs : as;
      tga += homeIsHere ? as : hs;
      if (hs > 0 && as > 0) bs += 1;
      if (hs + as > 2.5) o25 += 1;

      // Goal distribution buckets — uses goal events when available
      for (const ev of (p.goal_events || [])) {
        const b = bucketFor(ev.minute);
        const isHome = ev.team_id === homeTeamId;
        if (isHome) buckets.home_scored[b] += 1;
        else        buckets.home_conceded[b] += 1;
        if (ev.team_id === awayTeamId) buckets.away_scored[b] += 1;
        else if (ev.team_id) buckets.away_conceded[b] += 1;
      }
    }
    return {
      homeWins: hw, draws: d, awayWins: aw,
      totalGoalsHome: tgh, totalGoalsAway: tga,
      bothScored: bs, over25: o25,
      goalsByBucket: buckets,
    };
  }, [h2h, homeTeamId, awayTeamId]);

  const hasH2H = (h2h || []).length > 0;
  const matchesShown = matchesTeam === "home" ? homeTeamData : awayTeamData;

  return (
    <div data-testid="h2h-card">
      {/* Scoreline header — Sofascore mini panel */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-center text-center pb-4 mb-3 border-b" style={{ borderColor: "var(--cp-border)" }}>
        <div className="flex items-center justify-end gap-2">
          <span className="text-sm font-bold text-cp">{homeName}</span>
          <span className="text-lg font-extrabold tabular-nums" style={{ color: "#A3E635" }}>{homeWins}</span>
        </div>
        <span className="px-3 text-sm font-bold" style={{ color: "var(--cp-text-muted)" }}>{draws}</span>
        <div className="flex items-center justify-start gap-2">
          <span className="text-lg font-extrabold tabular-nums" style={{ color: "#7DD3FC" }}>{awayWins}</span>
          <span className="text-sm font-bold text-cp">{awayName}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* LEFT: Head-to-head matches */}
        <section className="cp-surface !bg-transparent ring-1 ring-white/5 rounded-lg p-3" data-testid="h2h-matches">
          <h4 className="text-center text-[13px] font-bold mb-3 pb-2 border-b" style={{ borderColor: "var(--cp-border)" }}>
            Head-to-head
          </h4>
          {hasH2H ? (
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
                    <span className="flex-1 truncate text-cp">
                      <span className={p.home_team_id === homeTeamId ? "font-semibold" : ""}>{p.home_team_name}</span>
                      <b className="mx-1.5 tabular-nums text-cp">{hs}-{as}</b>
                      <span className={p.away_team_id === homeTeamId ? "font-semibold" : ""}>{p.away_team_name}</span>
                    </span>
                    <OutcomePill outcome={outcome} />
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="text-center text-xs py-6" style={{ color: "var(--cp-text-muted)" }} data-testid="h2h-empty">
              No previous meetings between these teams yet.
            </div>
          )}
        </section>

        {/* RIGHT: Matches sidebar (Sofascore-style — recent + upcoming for chosen team) */}
        <section className="cp-surface !bg-transparent ring-1 ring-white/5 rounded-lg p-3" data-testid="h2h-team-matches">
          <h4 className="text-center text-[13px] font-bold mb-3 pb-2 border-b" style={{ borderColor: "var(--cp-border)" }}>
            Matches
          </h4>
          <div className="flex bg-white/5 rounded-full p-0.5 w-fit mx-auto mb-3 text-[11px]" data-testid="matches-team-toggle">
            <button
              onClick={() => setMatchesTeam("home")}
              className={`px-3 py-1 rounded-full transition ${matchesTeam === "home" ? "bg-cp-lime text-cp-forest font-bold" : "text-cp-muted"}`}
              data-testid="toggle-home"
            >{homeName}</button>
            <button
              onClick={() => setMatchesTeam("away")}
              className={`px-3 py-1 rounded-full transition ${matchesTeam === "away" ? "bg-cp-lime text-cp-forest font-bold" : "text-cp-muted"}`}
              data-testid="toggle-away"
            >{awayName}</button>
          </div>
          <TeamMatchesList data={matchesShown} pivotTeamId={matchesTeam === "home" ? homeTeamId : awayTeamId} />
        </section>
      </div>

      {/* Streaks + Goal distribution */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
        <section className="cp-surface !bg-transparent ring-1 ring-white/5 rounded-lg p-3" data-testid="h2h-streaks">
          <h4 className="text-center text-[13px] font-bold mb-3 pb-2 border-b" style={{ borderColor: "var(--cp-border)" }}>Streaks</h4>
          <div className="space-y-1.5">
            <Streak label={`${homeName} wins`} value={homeWins} accent="home" />
            <Streak label="Draws" value={draws} />
            <Streak label={`${awayName} wins`} value={awayWins} accent="away" />
            <Streak label={`Goals · ${homeName}`} value={totalGoalsHome} accent="home" />
            <Streak label={`Goals · ${awayName}`} value={totalGoalsAway} accent="away" />
            <Streak label="Both teams scored" value={hasH2H ? `${bothScored} / ${h2h.length}` : "—"} />
            <Streak label="Over 2.5 goals" value={hasH2H ? `${over25} / ${h2h.length}` : "—"} />
          </div>
        </section>

        <section className="cp-surface !bg-transparent ring-1 ring-white/5 rounded-lg p-3" data-testid="h2h-goal-distribution">
          <h4 className="text-center text-[13px] font-bold mb-3 pb-2 border-b" style={{ borderColor: "var(--cp-border)" }}>Goal distribution</h4>
          <GoalDistribution buckets={goalsByBucket} homeName={homeName} awayName={awayName} />
        </section>
      </div>
    </div>
  );
}

function TeamMatchesList({ data, pivotTeamId }) {
  if (!data) return <div className="text-xs text-center py-3" style={{ color: "var(--cp-text-muted)" }}>Loading…</div>;
  const recent = (data.recent_matches || []).slice(0, 5);
  const upcoming = (data.upcoming_matches || []).slice(0, 3);
  if (!recent.length && !upcoming.length) {
    return <div className="text-xs text-center py-3" style={{ color: "var(--cp-text-muted)" }}>No recent matches.</div>;
  }
  return (
    <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
      {upcoming.map((p) => (
        <MatchRow key={p.id} p={p} pivotTeamId={pivotTeamId} upcoming />
      ))}
      {recent.map((p) => (
        <MatchRow key={p.id} p={p} pivotTeamId={pivotTeamId} />
      ))}
    </ul>
  );
}

function MatchRow({ p, pivotTeamId, upcoming }) {
  const hs = Number(p.home_score ?? 0);
  const as = Number(p.away_score ?? 0);
  const date = p.scheduled_at ? new Date(p.scheduled_at) : null;
  let outcome = null;
  if (!upcoming) {
    if (hs === as) outcome = "D";
    else {
      const ourIsHome = p.home_team_id === pivotTeamId || p.home_team_name === pivotTeamId;
      outcome = (ourIsHome ? hs > as : as > hs) ? "W" : "L";
    }
  }
  return (
    <li className="flex items-center gap-2 py-2 text-[12px]">
      <span className="text-[10px] tabular-nums w-14 shrink-0" style={{ color: "var(--cp-text-muted)" }}>
        {date ? date.toLocaleDateString([], { day: "2-digit", month: "short", year: "2-digit" }) : "—"}
      </span>
      <span className="flex-1 truncate text-cp">
        <span>{p.home_team_name}</span>
        {upcoming ? (
          <b className="mx-1.5 tabular-nums" style={{ color: "var(--cp-text-muted)" }}>
            {date ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "vs"}
          </b>
        ) : (
          <b className="mx-1.5 tabular-nums text-cp">{hs}-{as}</b>
        )}
        <span>{p.away_team_name}</span>
      </span>
      {outcome && <OutcomePill outcome={outcome} />}
    </li>
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
    <div className="flex items-center justify-between py-1 text-[12px]">
      <span className="text-cp-muted truncate">{label}</span>
      <span className="font-bold tabular-nums shrink-0 ml-2" style={{ color: accentColor }}>{value}</span>
    </div>
  );
}

function GoalDistributionRow({ name, color, scored, conceded, maxVal, buckets: BUCKETS }) {
  return (
    <div className="mb-2">
      <div className="flex items-center justify-between text-[10px] mb-1">
        <span className="font-bold truncate" style={{ color }}>{name}</span>
        <span className="font-bold tabular-nums" style={{ color: "var(--cp-text-muted)" }}>
          {scored.reduce((a, b) => a + b, 0)} for · {conceded.reduce((a, b) => a + b, 0)} ag.
        </span>
      </div>
      <div className="grid grid-cols-6 gap-1">
        {BUCKETS.map((b, i) => {
          const s = scored[i] || 0;
          const c = conceded[i] || 0;
          const sh = (s / maxVal) * 28;
          const ch = (c / maxVal) * 28;
          return (
            <div key={b} className="flex flex-col items-center">
              <div className="flex items-end h-7 gap-0.5 w-full">
                <div className="flex-1 rounded-sm" style={{ height: `${Math.max(2, sh)}px`, background: color, opacity: s ? 1 : 0.15 }} title={`Scored ${s}`}/>
                <div className="flex-1 rounded-sm" style={{ height: `${Math.max(2, ch)}px`, background: "#EF4444", opacity: c ? 0.85 : 0.15 }} title={`Conceded ${c}`}/>
              </div>
              <span className="text-[9px] mt-1 tabular-nums" style={{ color: "var(--cp-text-muted)" }}>{b.split("-")[1]}&apos;</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GoalDistribution({ buckets, homeName, awayName }) {
  const BUCKETS = ["00-15", "15-30", "30-45", "45-60", "60-75", "75-90"];
  const maxVal = Math.max(1, ...buckets.home_scored, ...buckets.home_conceded, ...buckets.away_scored, ...buckets.away_conceded);
  return (
    <div data-testid="goal-distribution-chart">
      <GoalDistributionRow name={homeName} color="#A3E635" scored={buckets.home_scored} conceded={buckets.home_conceded} maxVal={maxVal} buckets={BUCKETS} />
      <GoalDistributionRow name={awayName} color="#7DD3FC" scored={buckets.away_scored} conceded={buckets.away_conceded} maxVal={maxVal} buckets={BUCKETS} />
      <div className="flex items-center justify-center gap-3 text-[9px] mt-2" style={{ color: "var(--cp-text-muted)" }}>
        <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: "#A3E635" }}/>Scored</span>
        <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: "#EF4444", opacity: 0.85 }}/>Conceded</span>
      </div>
    </div>
  );
}
