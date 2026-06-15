import React, { useEffect, useState } from "react";
import api from "../../lib/api";
import { Activity } from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, ReferenceLine, Tooltip,
} from "recharts";

/**
 * Attack Momentum — Sofascore-style stacked bar chart per minute.
 *   · Home pressure → positive Y, lime fill (#A3E635).
 *   · Away pressure → negative Y, slate fill (#94A3B8).
 *
 * Data flows from `/api/matches/{id}/momentum` (Sportmonks Pro `pressure[]`).
 * The endpoint is rate-limited at the network edge; we only fetch once per
 * mount. Empty/missing data shows the legacy small-state widget so the tab
 * doesn't render a giant empty card.
 */
const AttackMomentum = ({ matchId, homeTeamId, full = false }) => {
  const [data, setData] = useState(null);
  useEffect(() => {
    let mounted = true;
    api.get(`/matches/${matchId}/momentum`)
      .then(({ data }) => { if (mounted) setData(data); })
      .catch(() => mounted && setData({ momentum: [] }));
    return () => { mounted = false; };
  }, [matchId]);
  if (data === null) return null;
  const series = data.momentum || [];
  if (!series.length) {
    return (
      <div className="cp-surface p-3" data-testid="momentum-empty">
        <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Attack Momentum</div>
        <div className="flex items-center gap-2 mt-2 text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
          <Activity size={12}/> Will appear minute-by-minute once play starts.
        </div>
      </div>
    );
  }

  // Build per-minute rows for Recharts. Home goes up (+), away down (-).
  const byMin = {};
  for (const p of series) {
    const min = Number(p.minute) || 0;
    if (!byMin[min]) byMin[min] = { minute: min, home: 0, away: 0 };
    const isHome = p.team_id === (data.home_team_id || homeTeamId);
    const v = Math.max(0, Math.min(100, Number(p.value) || 0));
    if (isHome) byMin[min].home = Math.max(byMin[min].home, v);
    else        byMin[min].away = Math.max(byMin[min].away, v);
  }
  const minutes = Object.keys(byMin).map(Number).sort((a, b) => a - b);
  const max = minutes[minutes.length - 1] || 90;
  // Recharts needs negative-Y for the away bars to stack below the centerline.
  const rows = minutes.map((m) => ({ minute: m, home: byMin[m].home, away: -byMin[m].away }));

  const small = !full;
  const chartHeight = small ? 80 : 240;

  return (
    <div className="cp-surface p-3 sm:p-4" data-testid="attack-momentum">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[10px] sm:text-xs uppercase tracking-widest font-bold" style={{ color: "var(--cp-text-muted)" }}>
          Attack Momentum
        </div>
        <div className="flex items-center gap-2 text-[10px] sm:text-xs">
          <span className="inline-flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: "#A3E635" }}/>Home</span>
          <span className="inline-flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: "#94A3B8" }}/>Away</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart data={rows} stackOffset="sign" margin={{ top: 4, right: 4, bottom: 4, left: 0 }} barCategoryGap={1}>
          <XAxis dataKey="minute" hide />
          <YAxis hide domain={[-100, 100]} />
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.22)" />
          <ReferenceLine x={45} stroke="rgba(255,255,255,0.18)" strokeDasharray="3 3" />
          {full && (
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              contentStyle={{
                background: "var(--cp-surface-2, #252A32)",
                border: "1px solid var(--cp-border, #2A2E36)",
                borderRadius: 6, fontSize: 12,
              }}
              labelFormatter={(min) => `Minute ${min}'`}
              formatter={(value, key) => [`${Math.abs(value).toFixed(0)}%`, key === "home" ? "Home" : "Away"]}
            />
          )}
          <Bar dataKey="home" stackId="m" fill="#A3E635" isAnimationActive={false} />
          <Bar dataKey="away" stackId="m" fill="#94A3B8" isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <div className="flex justify-between text-[9px] sm:text-[10px] mt-1" style={{ color: "var(--cp-text-muted)" }}>
        <span>0&apos;</span><span>HT</span><span>{max}&apos;</span>
      </div>
    </div>
  );
};

export default AttackMomentum;
