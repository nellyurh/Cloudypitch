import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { Trophy, Target } from "lucide-react";

export const Leaderboards = () => {
  const [tab, setTab] = useState("predictions");
  const [pred, setPred] = useState([]);
  const [fan, setFan] = useState([]);
  useEffect(() => { (async () => {
    try { const [p, f] = await Promise.all([api.get("/predictions/leaderboard?limit=100"), api.get("/fantasy/leaderboard?limit=100")]);
      setPred(p.data.leaderboard || []); setFan(f.data.leaderboard || []); } catch (_) {}
  })(); }, []);
  const rows = tab === "predictions" ? pred : fan;
  return (
    <div data-testid="leaderboards-page">
      <h1 className="text-2xl font-extrabold mb-3">Leaderboards</h1>
      <div className="flex gap-1 cp-surface p-1 w-fit mb-3">
        <button onClick={() => setTab("predictions")} className={`px-3 py-1.5 text-sm rounded transition flex items-center gap-1.5 ${tab === "predictions" ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid="lb-tab-predictions"><Target size={12}/> Predictions</button>
        <button onClick={() => setTab("fantasy")} className={`px-3 py-1.5 text-sm rounded transition flex items-center gap-1.5 ${tab === "fantasy" ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid="lb-tab-fantasy"><Trophy size={12}/> Fantasy</button>
      </div>
      <div className="cp-surface overflow-hidden">
        {rows.length === 0 && <div className="p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>No leaderboard data yet.</div>}
        <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
          {rows.map(r => (
            <li key={r.user_id} className="px-3 py-2 flex items-center gap-3 text-sm" data-testid={`lb-row-${r.user_id}`}>
              <span className="cp-logo-circle text-[10px]" style={{ width: 26, height: 26, background: r.rank <= 3 ? "#A3E635" : "var(--cp-surface-2)", color: r.rank <= 3 ? "#064E3B" : "var(--cp-text)" }}>{r.rank}</span>
              <div className="flex-1 min-w-0">
                <div className="truncate font-medium">{r.display_name || r.squad_name}</div>
                <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{r.country_code || "NG"}{tab === "predictions" ? ` · ${r.predictions_made} picks · ${r.exact_scores} exact` : ""}</div>
              </div>
              <span className="text-cp-lime font-extrabold tabular-nums">{r.total_points || 0}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default Leaderboards;
