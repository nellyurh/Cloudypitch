import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth, formatApiErr } from "../lib/auth";
import { Link } from "react-router-dom";
import { Trophy, Check, AlertTriangle } from "lucide-react";

export const PredictionsHub = () => {
  const { user } = useAuth();
  const [matches, setMatches] = useState([]);
  const [board, setBoard] = useState([]);
  const [picks, setPicks] = useState({}); // { matchId: { home, away } }
  const [saving, setSaving] = useState({});
  const [err, setErr] = useState("");

  const load = async () => {
    try {
      const [u, b] = await Promise.all([
        api.get("/predictions/upcoming?limit=50"),
        api.get("/predictions/leaderboard?limit=10"),
      ]);
      setMatches(u.data.matches || []);
      setBoard(b.data.leaderboard || []);
      const init = {};
      for (const m of u.data.matches || []) {
        if (m.my_prediction) init[m.id] = { home: m.my_prediction.home_score_predicted, away: m.my_prediction.away_score_predicted };
      }
      setPicks(p => ({ ...init, ...p }));
    } catch (_) {}
  };

  useEffect(() => { load(); }, []);

  const submit = async (matchId) => {
    const p = picks[matchId];
    if (!p || p.home == null || p.away == null) return;
    setSaving(s => ({ ...s, [matchId]: true }));
    setErr("");
    try {
      await api.post("/predictions", { match_id: matchId, home_score_predicted: Number(p.home), away_score_predicted: Number(p.away) });
    } catch (e) { setErr(formatApiErr(e)); }
    setSaving(s => ({ ...s, [matchId]: false }));
    load();
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4" data-testid="predictions-hub">
      <div>
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-xl font-extrabold tracking-tight">Make Your Predictions <span className="text-cp-lime">·</span> <span style={{ color: "var(--cp-text-muted)" }} className="text-sm font-medium">10 pts exact · 6 pts diff · 4 pts outcome</span></h1>
          {!user && <Link to="/signin" className="cp-btn-primary" data-testid="pred-signin-cta">Sign in to play</Link>}
        </div>

        {err && <div className="cp-surface p-3 text-sm mb-3 flex items-center gap-2" style={{ borderColor: "#FF3D52", color: "#FF3D52" }}><AlertTriangle size={14}/>{err}</div>}

        {matches.length === 0 && <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>No upcoming matches yet. Check back soon.</div>}

        <div className="space-y-2">
          {matches.map(m => {
            const p = picks[m.id] || {};
            const locked = !user;
            return (
              <div key={m.id} className="cp-surface p-3" data-testid={`pred-match-${m.id}`}>
                <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{m.league_country} · {m.league_name}</div>
                <div className="text-[11px] mt-0.5" style={{ color: "var(--cp-text-muted)" }}>{new Date(m.scheduled_at).toLocaleString()}</div>
                <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 mt-2">
                  <div className="text-right truncate font-medium" data-testid={`pred-home-${m.id}`}>{m.home_team_name}</div>
                  <div className="flex items-center gap-2">
                    <input type="number" min="0" max="20" value={p.home ?? ""} disabled={locked} onChange={(e) => setPicks(prev => ({ ...prev, [m.id]: { ...prev[m.id], home: e.target.value } }))} className="cp-input !w-14 text-center" data-testid={`input-home-${m.id}`}/>
                    <span style={{ color: "var(--cp-text-muted)" }}>:</span>
                    <input type="number" min="0" max="20" value={p.away ?? ""} disabled={locked} onChange={(e) => setPicks(prev => ({ ...prev, [m.id]: { ...prev[m.id], away: e.target.value } }))} className="cp-input !w-14 text-center" data-testid={`input-away-${m.id}`}/>
                  </div>
                  <div className="truncate font-medium" data-testid={`pred-away-${m.id}`}>{m.away_team_name}</div>
                </div>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
                    {m.my_prediction ? <><Check size={11} className="inline text-cp-lime mr-1"/>Predicted</> : "Not yet predicted"}
                  </span>
                  <button onClick={() => submit(m.id)} disabled={locked || saving[m.id]} className="cp-btn-primary !py-1.5 disabled:opacity-50" data-testid={`pred-submit-${m.id}`}>
                    {saving[m.id] ? "Saving…" : (m.my_prediction ? "Update Pick" : "Submit Pick")}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <aside className="cp-surface h-fit lg:sticky lg:top-[110px]" data-testid="pred-leaderboard">
        <div className="cp-card-header normal-case">
          <span className="flex items-center gap-2 font-bold" style={{ color: "var(--cp-text)" }}><Trophy size={14} className="text-cp-lime"/> Top Predictors</span>
        </div>
        <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
          {board.length === 0 && <li className="p-4 text-sm" style={{ color: "var(--cp-text-muted)" }}>No scores yet.</li>}
          {board.map(r => (
            <li key={r.user_id} className="px-3 py-2 flex items-center gap-2 text-sm">
              <span className="cp-logo-circle text-[10px]" style={{ width: 22, height: 22 }}>{r.rank}</span>
              <span className="truncate flex-1">{r.display_name}</span>
              <span className="tabular-nums font-bold text-cp-lime">{r.total_points}</span>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
};

export default PredictionsHub;
