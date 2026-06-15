import React, { useMemo } from "react";

/**
 * Sofascore-style H2H card with W-D-L aggregate badges + match rows.
 * Aggregates are computed from the home team's perspective.
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

  return (
    <div data-testid="h2h-card">
      {/* Aggregate header — W / D / L pills */}
      <div className="mb-4 pb-4 border-b" style={{ borderColor: "var(--cp-border)" }}>
        <div className="text-[10px] uppercase tracking-[0.1em] font-semibold text-center mb-3" style={{ color: "var(--cp-text-muted)" }}>
          Last {h2h.length} meetings · from {homeName}&apos;s view
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Badge label="Wins" value={wins} tone="win" testId="h2h-wins" />
          <Badge label="Draws" value={draws} tone="draw" testId="h2h-draws" />
          <Badge label="Losses" value={losses} tone="loss" testId="h2h-losses" />
        </div>
      </div>

      {/* Match rows */}
      <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }} data-testid="h2h-list">
        {h2h.map((p) => {
          const hs = Number(p.home_score ?? 0);
          const as = Number(p.away_score ?? 0);
          const homeIsOurTeam = p.home_team_id === homeTeamId;
          let outcome;
          if (hs === as) outcome = "D";
          else outcome = (homeIsOurTeam ? hs > as : as > hs) ? "W" : "L";

          const date = p.scheduled_at ? new Date(p.scheduled_at) : null;

          return (
            <li key={p.id} className="flex items-center gap-3 py-2.5 text-sm" data-testid={`h2h-row-${p.id}`}>
              <span className="text-[10px] tabular-nums w-14 shrink-0" style={{ color: "var(--cp-text-muted)" }}>
                {date ? date.toLocaleDateString([], { day: "2-digit", month: "short", year: "2-digit" }) : "—"}
              </span>
              <span className="flex-1 truncate text-slate-200">
                <span className={p.home_team_id === homeTeamId ? "font-bold" : ""}>{p.home_team_name}</span>
                <b className="mx-2 tabular-nums text-slate-100">{hs}–{as}</b>
                <span className={p.away_team_id === homeTeamId ? "font-bold" : ""}>{p.away_team_name}</span>
              </span>
              <OutcomePill outcome={outcome} />
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Badge({ label, value, tone, testId }) {
  const tones = {
    win:  { bg: "rgba(34,197,94,0.12)",  border: "rgba(34,197,94,0.35)",  fg: "#22C55E" },
    draw: { bg: "rgba(148,163,184,0.12)", border: "rgba(148,163,184,0.3)", fg: "#94A3B8" },
    loss: { bg: "rgba(239,68,68,0.12)",  border: "rgba(239,68,68,0.35)",  fg: "#EF4444" },
  };
  const c = tones[tone] || tones.draw;
  return (
    <div
      className="flex flex-col items-center justify-center rounded-lg py-2.5 border"
      style={{ background: c.bg, borderColor: c.border }}
      data-testid={testId}
    >
      <div className="text-2xl font-extrabold tabular-nums leading-none" style={{ color: c.fg }}>{value}</div>
      <div className="text-[10px] uppercase tracking-wider mt-1" style={{ color: c.fg, opacity: 0.85 }}>{label}</div>
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
