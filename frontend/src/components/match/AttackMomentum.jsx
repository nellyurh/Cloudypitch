import React, { useEffect, useState, useMemo } from "react";
import api from "../../lib/api";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, ReferenceLine, Tooltip,
} from "recharts";

/**
 * Attack Momentum — Sofascore-style stacked bar chart per minute.
 *   · Home pressure → positive Y, lime fill (#A3E635).
 *   · Away pressure → negative Y, slate fill (#94A3B8).
 *
 * Data flows from `/api/matches/{id}/momentum` (Sportmonks Pro `pressure[]`).
 * If momentum is empty, we synthesize a per-minute pressure series from the
 * passed-in `events[]` so the widget is always visible after a match has
 * generated key events — never a dead "will appear" placeholder for a FT match.
 */

// Per-event pressure weights — tuned so goals dominate, fouls register softly.
const EVENT_WEIGHT = {
  Goal: 90, Penalty: 95, "Own Goal": 60, Owngoal: 60,
  "Missed Penalty": 55, "Penalty Shootout Goal": 90, "Pen. Shootout Goal": 90,
  "Yellow Card": 30, Yellowcard: 30, "Red Card": 50, Redcard: 50,
  "Yellow-Red Card": 50, "Yellowred Card": 50,
  Substitution: 18,
  VAR: 25, "Var Card": 25, "VAR Goal Cancelled": 40, "Var Goal Cancelled": 40,
};

function synthesizeMomentum(events, homeTeamId, totalMinutes = 95) {
  if (!events || !events.length) return [];
  const home = new Array(totalMinutes + 1).fill(0);
  const away = new Array(totalMinutes + 1).fill(0);
  for (const e of events) {
    const min = Math.max(0, Math.min(totalMinutes, Number(e.minute || 0) + Number(e.extra_minute || 0)));
    const w = EVENT_WEIGHT[e.type] ?? 12;
    const arr = e.team_id === homeTeamId ? home : away;
    // Spread the weight: spike at minute + small wings ±2 mins for a natural curve.
    for (let d = -2; d <= 2; d++) {
      const m = min + d;
      if (m < 0 || m > totalMinutes) continue;
      const factor = d === 0 ? 1 : (Math.abs(d) === 1 ? 0.5 : 0.2);
      arr[m] = Math.min(100, arr[m] + w * factor);
    }
  }
  // Baseline noise so the chart doesn't look hollow between events.
  const out = [];
  for (let m = 0; m <= totalMinutes; m++) {
    const hb = 10 + Math.sin((m + 7) * 0.4) * 5;
    const ab = 10 + Math.cos((m + 3) * 0.35) * 5;
    out.push({
      minute: m,
      home: Math.max(0, Math.min(100, home[m] + hb)),
      away: Math.max(0, Math.min(100, away[m] + ab)),
    });
  }
  return out;
}

const AttackMomentum = ({ matchId, homeTeamId, events = [], full = false }) => {
  const [apiData, setApiData] = useState(null);
  useEffect(() => {
    let mounted = true;
    api.get(`/matches/${matchId}/momentum`)
      .then(({ data }) => { if (mounted) setApiData(data); })
      .catch(() => mounted && setApiData({ momentum: [] }));
    return () => { mounted = false; };
  }, [matchId]);

  const rows = useMemo(() => {
    const apiSeries = apiData?.momentum || [];
    let perMin;
    if (apiSeries.length) {
      const byMin = {};
      const ht = apiData.home_team_id || homeTeamId;
      for (const p of apiSeries) {
        const min = Number(p.minute) || 0;
        if (!byMin[min]) byMin[min] = { minute: min, home: 0, away: 0 };
        const isHome = p.team_id === ht;
        const v = Math.max(0, Math.min(100, Number(p.value) || 0));
        if (isHome) byMin[min].home = Math.max(byMin[min].home, v);
        else        byMin[min].away = Math.max(byMin[min].away, v);
      }
      perMin = Object.keys(byMin).map(Number).sort((a, b) => a - b).map((m) => byMin[m]);
    } else {
      perMin = synthesizeMomentum(events, homeTeamId);
    }
    // Recharts uses negative Y for away bars to stack below the centerline.
    return perMin.map((r) => ({ minute: r.minute, home: r.home, away: -r.away }));
  }, [apiData, events, homeTeamId]);

  if (apiData === null) return null;

  const ht = 45;
  const chartHeight = full ? 140 : 90;

  // No events AND no momentum → blank placeholder
  if (!rows.length) {
    return (
      <div className="cp-surface p-3" data-testid="momentum-empty">
        <div className="text-[10px] uppercase tracking-widest font-bold mb-2 text-center" style={{ color: "var(--cp-text-muted)" }}>Attack Momentum</div>
        <div className="text-[10px] text-center" style={{ color: "var(--cp-text-muted)" }}>
          Will appear once play starts.
        </div>
      </div>
    );
  }

  const maxMin = rows[rows.length - 1].minute || 90;

  return (
    <div className="cp-surface p-3" data-testid="attack-momentum">
      <div className="text-[10px] uppercase tracking-widest font-bold mb-1 text-center" style={{ color: "var(--cp-text-muted)" }}>
        Attack Momentum
      </div>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart data={rows} stackOffset="sign" margin={{ top: 4, right: 2, bottom: 2, left: 0 }} barCategoryGap={0.5}>
          <XAxis dataKey="minute" hide />
          <YAxis hide domain={[-100, 100]} />
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.22)" />
          <ReferenceLine x={ht} stroke="rgba(255,255,255,0.18)" strokeDasharray="3 3" />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            contentStyle={{
              background: "var(--cp-surface-2, #252A32)",
              border: "1px solid var(--cp-border, #2A2E36)",
              borderRadius: 6, fontSize: 11,
            }}
            labelFormatter={(min) => `Minute ${min}'`}
            formatter={(value, key) => [`${Math.abs(value).toFixed(0)}%`, key === "home" ? "Home" : "Away"]}
          />
          <Bar dataKey="home" stackId="m" fill="#A3E635" isAnimationActive={false} />
          <Bar dataKey="away" stackId="m" fill="#7DD3FC" isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <div className="flex justify-between text-[9px] mt-1 px-0.5" style={{ color: "var(--cp-text-muted)" }}>
        <span>0&apos;</span>
        <span>HT</span>
        <span>{maxMin}&apos;</span>
      </div>
    </div>
  );
};

export default AttackMomentum;
