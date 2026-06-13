import React, { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { useAuth, formatApiErr } from "../lib/auth";
import { Link } from "react-router-dom";
import { Trophy, Check, AlertTriangle, Lock, Award, Crown, History, X } from "lucide-react";
import RewardedVideoButton from "../components/RewardedVideoButton";

const TeamLogo = ({ src, name }) => {
  if (src) return <img src={src} alt="" className="w-6 h-6 object-contain shrink-0" onError={(e) => { e.target.style.display = "none"; }}/>;
  return (
    <span className="inline-flex items-center justify-center w-6 h-6 rounded-sm text-[10px] font-bold shrink-0" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>
      {(name || "?").slice(0, 1).toUpperCase()}
    </span>
  );
};

function groupByDate(matches) {
  const groups = {};
  for (const m of matches) {
    const d = new Date(m.scheduled_at);
    const key = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
    if (!groups[key]) groups[key] = [];
    groups[key].push(m);
  }
  return Object.entries(groups);
}

const STATUS_PILL = (s) => {
  if (["FT", "AET", "PEN"].includes(s)) return { label: "FT", color: "#A3E635", bg: "rgba(163,230,53,0.15)" };
  if (["1H", "2H", "HT", "LIVE", "ET"].includes(s)) return { label: "LIVE", color: "#FF3D52", bg: "rgba(255,61,82,0.15)" };
  return { label: "Soon", color: "var(--cp-text-muted)", bg: "var(--cp-surface-2)" };
};

function MyPredictionsList({ data }) {
  const list = data?.predictions || [];
  if (list.length === 0) {
    return (
      <div className="cp-surface p-8 text-center" data-testid="my-predictions-empty">
        <History size={36} className="mx-auto text-cp-lime opacity-60"/>
        <h3 className="text-base font-bold mt-3">No predictions yet</h3>
        <p className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>Switch to <b>Upcoming</b> and make your first picks.</p>
      </div>
    );
  }
  return (
    <div data-testid="my-predictions-list">
      <div className="cp-surface p-3 mb-3 grid grid-cols-3 gap-3 text-center">
        <div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Total Picks</div>
          <div className="text-2xl font-extrabold tabular-nums">{list.length}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Settled</div>
          <div className="text-2xl font-extrabold tabular-nums">{data.settled_count || 0}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Total Points</div>
          <div className="text-2xl font-extrabold tabular-nums text-cp-lime">{data.total_points || 0}</div>
        </div>
      </div>
      <div className="cp-surface divide-y" style={{ borderColor: "var(--cp-border)" }}>
        {list.map(p => {
          const m = p.match || {};
          const settled = !!p.settled_at;
          const pill = STATUS_PILL(m.status);
          const correctOutcome = !!p.outcome_correct;
          const exact = !!p.exact_score_hit;
          return (
            <div key={p.id} className="px-3 py-3" data-testid={`my-pred-${p.match_id}`}>
              <div className="flex items-center justify-between text-[10px] uppercase tracking-widest mb-2" style={{ color: "var(--cp-text-muted)" }}>
                <span className="truncate">{m.league_country || ""}{m.league_country ? " · " : ""}{m.league_name || "World Cup 2026"}</span>
                <span className="cp-pill !text-[9px] !font-bold" style={{ background: pill.bg, color: pill.color }}>{pill.label}</span>
              </div>
              <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
                <div className="flex items-center gap-2 justify-end min-w-0">
                  <span className="truncate font-medium text-right">{m.home_team_name || "Home"}</span>
                  <TeamLogo src={m.home_team_logo} name={m.home_team_name}/>
                </div>
                <div className="flex flex-col items-center gap-0.5 min-w-[80px]">
                  {/* Actual result if available */}
                  {(m.status && ["FT","AET","PEN","1H","2H","HT","LIVE","ET"].includes(m.status)) ? (
                    <div className="text-base font-extrabold tabular-nums" data-testid={`my-pred-result-${p.match_id}`}>
                      {m.home_score ?? 0}–{m.away_score ?? 0}
                    </div>
                  ) : (
                    <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
                      {m.scheduled_at ? new Date(m.scheduled_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "TBD"}
                    </div>
                  )}
                  <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>your pick</div>
                  <div className="text-sm font-bold tabular-nums" style={{ color: exact ? "#A3E635" : correctOutcome ? "#FBBF24" : settled ? "#FF3D52" : "var(--cp-text)" }} data-testid={`my-pred-pick-${p.match_id}`}>
                    {p.home_score_predicted}–{p.away_score_predicted}
                  </div>
                </div>
                <div className="flex items-center gap-2 min-w-0">
                  <TeamLogo src={m.away_team_logo} name={m.away_team_name}/>
                  <span className="truncate font-medium">{m.away_team_name || "Away"}</span>
                </div>
              </div>
              <div className="flex items-center justify-between mt-2 flex-wrap gap-2">
                <div className="flex items-center gap-2 text-[11px]">
                  {settled ? (
                    exact ? (
                      <span className="cp-pill !text-[10px] !font-bold inline-flex items-center gap-1" style={{ background: "rgba(163,230,53,0.18)", color: "#A3E635" }}>
                        <Check size={11}/> Exact score!
                      </span>
                    ) : correctOutcome ? (
                      <span className="cp-pill !text-[10px] !font-bold inline-flex items-center gap-1" style={{ background: "rgba(251,191,36,0.18)", color: "#FBBF24" }}>
                        <Check size={11}/> Outcome correct
                      </span>
                    ) : (
                      <span className="cp-pill !text-[10px] !font-bold inline-flex items-center gap-1" style={{ background: "rgba(255,61,82,0.15)", color: "#FF3D52" }}>
                        <X size={11}/> Missed
                      </span>
                    )
                  ) : (
                    <span className="cp-pill !text-[10px] !font-bold inline-flex items-center gap-1" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>
                      <Lock size={10}/> Pending settlement
                    </span>
                  )}
                  {p.stage && p.stage !== "any" && (
                    <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{p.stage} ×{p.stage_multiplier || 1}</span>
                  )}
                  {p.streak_bonus > 0 && (
                    <span className="text-[10px]" style={{ color: "#A3E635" }}>+{p.streak_bonus} streak</span>
                  )}
                </div>
                <div className="text-right">
                  <span className="text-[10px] uppercase tracking-widest mr-1" style={{ color: "var(--cp-text-muted)" }}>Points</span>
                  <span className="text-base font-extrabold tabular-nums text-cp-lime" data-testid={`my-pred-points-${p.match_id}`}>{p.points_awarded || 0}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export const PredictionsHub = () => {
  const { user } = useAuth();
  const [matches, setMatches] = useState([]);
  const [board, setBoard] = useState([]);
  const [boardScope, setBoardScope] = useState("global");
  const [picks, setPicks] = useState({});
  const [saving, setSaving] = useState({});
  const [savedMatch, setSavedMatch] = useState(null);
  const [err, setErr] = useState("");
  // 'upcoming' = make new picks. 'mine' = review my closed/past predictions.
  const [tab, setTab] = useState("upcoming");
  const [mine, setMine] = useState({ predictions: [], total_points: 0, exact_count: 0, settled_count: 0 });

  const load = async () => {
    try {
      const calls = [
        api.get("/predictions/upcoming?limit=80"),
        api.get(`/leaderboard?limit=10&scope=${boardScope}`),
      ];
      if (user) calls.push(api.get("/predictions/me?limit=200"));
      const results = await Promise.all(calls);
      const [u, b, me] = results;
      setMatches(u.data.matches || []);
      setBoard(b.data.leaderboard || []);
      if (me) setMine(me.data || { predictions: [] });
      const init = {};
      for (const m of u.data.matches || []) {
        if (m.my_prediction) init[m.id] = { home: m.my_prediction.home_score_predicted, away: m.my_prediction.away_score_predicted };
      }
      setPicks(p => ({ ...init, ...p }));
    } catch (_) {}
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [boardScope, user?.id]);

  const submit = async (matchId) => {
    const p = picks[matchId];
    if (!p || p.home == null || p.away == null) return;
    setSaving(s => ({ ...s, [matchId]: true }));
    setErr("");
    try {
      await api.post("/predictions", {
        match_id: matchId,
        home_score_predicted: Number(p.home),
        away_score_predicted: Number(p.away),
      });
      setSavedMatch(matchId);
      setTimeout(() => setSavedMatch(null), 1800);
    } catch (e) { setErr(formatApiErr(e)); }
    setSaving(s => ({ ...s, [matchId]: false }));
    load();
  };

  const myTotalPoints = useMemo(() => {
    if (!user) return 0;
    const mine = board.find(b => b.user_id === user.id);
    return mine?.total_points || 0;
  }, [board, user]);

  const myRank = useMemo(() => {
    if (!user) return null;
    const mine = board.find(b => b.user_id === user.id);
    return mine?.rank || null;
  }, [board, user]);

  const grouped = useMemo(() => groupByDate(matches), [matches]);
  const total = matches.length;
  const predicted = matches.filter(m => m.my_prediction).length;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4" data-testid="predictions-hub">
      <div>
        <div className="cp-surface p-4 mb-3 flex flex-wrap items-center gap-3 justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>FIFA World Cup 2026 · Predictions</div>
            <h1 className="text-xl font-extrabold tracking-tight mt-0.5">Make Your Picks</h1>
            <div className="text-[11px] mt-1" style={{ color: "var(--cp-text-muted)" }}>
              <span className="text-cp-lime font-bold">30 pts</span> exact · <span className="text-cp-lime font-bold">15 pts</span> goal diff · <span className="text-cp-lime font-bold">10 pts</span> outcome
              <br/>
              <span className="opacity-80">WC stage × up to 4.0 · 3-streak +10 · 5-streak +25 · 10-streak +100 · Apply boost cards for additional %</span>
            </div>
          </div>
          {user ? (
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Your Total</div>
                <div className="text-2xl font-extrabold text-cp-lime tabular-nums" data-testid="my-points">{myTotalPoints}</div>
              </div>
              {myRank && (
                <div className="text-right">
                  <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Rank</div>
                  <div className="text-2xl font-extrabold tabular-nums">#{myRank}</div>
                </div>
              )}
              <div className="text-right">
                <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Picks</div>
                <div className="text-2xl font-extrabold tabular-nums">{predicted}<span className="text-sm font-normal" style={{ color: "var(--cp-text-muted)" }}>/{total}</span></div>
              </div>
            </div>
          ) : (
            <Link to="/signin" className="cp-btn-primary" data-testid="pred-signin-cta">Sign in to play</Link>
          )}
        </div>

        {err && <div className="cp-surface p-3 text-sm mb-3 flex items-center gap-2" style={{ borderColor: "#FF3D52", color: "#FF3D52" }}><AlertTriangle size={14}/>{err}</div>}

        {user && (
          <div className="flex gap-1 cp-surface p-1 mb-3 w-fit" data-testid="pred-tabs">
            <button
              onClick={() => setTab("upcoming")}
              className={`px-3 py-1.5 text-xs rounded font-bold inline-flex items-center gap-1.5 ${tab === "upcoming" ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`}
              style={{ color: tab === "upcoming" ? "#064E3B" : "var(--cp-text)" }}
              data-testid="pred-tab-upcoming"
            >
              <Award size={12}/> Upcoming
            </button>
            <button
              onClick={() => setTab("mine")}
              className={`px-3 py-1.5 text-xs rounded font-bold inline-flex items-center gap-1.5 ${tab === "mine" ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`}
              style={{ color: tab === "mine" ? "#064E3B" : "var(--cp-text)" }}
              data-testid="pred-tab-mine"
            >
              <History size={12}/> My Picks ({mine.predictions.length})
            </button>
          </div>
        )}

        {tab === "mine" && user ? (
          <MyPredictionsList data={mine}/>
        ) : (
        <>
        {matches.length === 0 && (
          <div className="cp-surface p-8 text-center" data-testid="predictions-empty">
            <Trophy size={36} className="mx-auto text-cp-lime opacity-60"/>
            <h3 className="text-base font-bold mt-3">FIFA WC 2026 fixtures load on draw day</h3>
            <p className="text-xs mt-1 max-w-md mx-auto" style={{ color: "var(--cp-text-muted)" }}>
              Predictions are available exclusively for World Cup 2026 matches. The first batch of fixtures will appear here when FIFA publishes the official draw.
            </p>
          </div>
        )}

        <div className="space-y-4">
          {grouped.map(([date, list]) => (
            <section key={date}>
              <h2 className="text-[11px] uppercase tracking-widest mb-2 px-1 flex items-center gap-2" style={{ color: "var(--cp-text-muted)" }}>
                <Award size={12} className="text-cp-lime"/> {date}
                <span className="ml-auto">{list.length} match{list.length === 1 ? "" : "es"}</span>
              </h2>
              <div className="cp-surface divide-y" style={{ borderColor: "var(--cp-border)" }}>
                {list.map(m => {
                  const p = picks[m.id] || {};
                  const locked = !user || (m.is_live || ["FT","AET","PEN","1H","2H","HT","LIVE","ET"].includes(m.status));
                  const predicted = !!m.my_prediction;
                  return (
                    <div key={m.id} className="px-3 py-3" data-testid={`pred-match-${m.id}`}>
                      <div className="flex items-center justify-between text-[10px] uppercase tracking-widest mb-2" style={{ color: "var(--cp-text-muted)" }}>
                        <span className="truncate">{m.league_country} · {m.league_name}</span>
                        <span className="tabular-nums">{new Date(m.scheduled_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })}</span>
                      </div>
                      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
                        <div className="flex items-center gap-2 justify-end min-w-0" data-testid={`pred-home-${m.id}`}>
                          <span className="truncate font-medium text-right">{m.home_team_name}</span>
                          <TeamLogo src={m.home_team_logo} name={m.home_team_name}/>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <input
                            type="number" min="0" max="20"
                            value={p.home ?? ""} disabled={locked}
                            onChange={(e) => setPicks(prev => ({ ...prev, [m.id]: { ...prev[m.id], home: e.target.value } }))}
                            className="cp-input !w-12 text-center text-base font-bold tabular-nums"
                            data-testid={`input-home-${m.id}`}
                          />
                          <span className="font-bold" style={{ color: "var(--cp-text-muted)" }}>:</span>
                          <input
                            type="number" min="0" max="20"
                            value={p.away ?? ""} disabled={locked}
                            onChange={(e) => setPicks(prev => ({ ...prev, [m.id]: { ...prev[m.id], away: e.target.value } }))}
                            className="cp-input !w-12 text-center text-base font-bold tabular-nums"
                            data-testid={`input-away-${m.id}`}
                          />
                        </div>
                        <div className="flex items-center gap-2 min-w-0" data-testid={`pred-away-${m.id}`}>
                          <TeamLogo src={m.away_team_logo} name={m.away_team_name}/>
                          <span className="truncate font-medium">{m.away_team_name}</span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-[11px] inline-flex items-center gap-1" style={{ color: predicted ? "#A3E635" : "var(--cp-text-muted)" }}>
                          {locked && !predicted ? (
                            <><Lock size={11}/> Locked</>
                          ) : predicted ? (
                            <><Check size={11}/> Predicted {p.home}-{p.away}{m.my_prediction.points_earned != null ? ` · ${m.my_prediction.points_earned}pts` : ""}</>
                          ) : (
                            "Not yet predicted"
                          )}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => submit(m.id)}
                            disabled={locked || saving[m.id] || p.home == null || p.away == null || p.home === "" || p.away === ""}
                            className="cp-btn-primary !py-1 !text-xs disabled:opacity-40"
                            data-testid={`pred-submit-${m.id}`}
                          >
                            {savedMatch === m.id ? "Saved!" : saving[m.id] ? "Saving…" : (predicted ? "Update" : "Submit")}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
        </>
        )}
      </div>

      <aside className="cp-surface h-fit lg:sticky lg:top-[110px]" data-testid="pred-leaderboard">
        <div className="cp-card-header normal-case">
          <span className="flex items-center gap-2 font-bold" style={{ color: "var(--cp-text)" }}><Trophy size={14} className="text-cp-lime"/> Top Predictors</span>
        </div>
        <div className="flex gap-1 px-2 pt-2">
          {[
            { k: "global", label: "Global" },
            { k: "weekly", label: "Weekly" },
            { k: "premium", label: "Premium", premium: true },
          ].map(t => (
            <button
              key={t.k}
              onClick={() => setBoardScope(t.k)}
              className={`px-2 py-1 text-[10px] rounded font-bold inline-flex items-center gap-1 ${boardScope === t.k ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`}
              style={{ color: boardScope === t.k ? "#064E3B" : "var(--cp-text)" }}
              data-testid={`board-tab-${t.k}`}
            >
              {t.premium && <Crown size={10} className="text-cp-lime"/>}
              {t.label}
            </button>
          ))}
        </div>
        {boardScope === "premium" && !user?.is_premium && (
          <div className="text-[10px] mt-1 px-3 pb-1" style={{ color: "var(--cp-text-muted)" }}>
            Premium-only side leaderboard. <Link to="/premium" className="text-cp-lime">Upgrade $2/mo</Link>
          </div>
        )}
        <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
          {board.length === 0 && <li className="p-4 text-sm" style={{ color: "var(--cp-text-muted)" }}>No scores yet — be the first!</li>}
          {board.map(r => (
            <li key={r.user_id} className={`px-3 py-2 flex items-center gap-2 text-sm ${user && r.user_id === user.id ? "bg-cp-lime/10" : ""}`}>
              <span className="cp-logo-circle text-[10px] font-extrabold" style={{ width: 22, height: 22, background: r.rank === 1 ? "#A3E635" : "var(--cp-surface-2)", color: r.rank === 1 ? "#064E3B" : "var(--cp-text)" }}>{r.rank}</span>
              <span className="truncate flex-1">{r.display_name}</span>
              {r.potential_prize_usd_cents > 0 && (
                <span className="text-[10px] tabular-nums" style={{ color: "#A3E635" }}>${(r.potential_prize_usd_cents / 100).toFixed(0)}</span>
              )}
              <span className="tabular-nums font-bold text-cp-lime">{r.total_points}</span>
            </li>
          ))}
        </ul>
        {user && (
          <div className="p-3 border-t" style={{ borderColor: "var(--cp-border)" }}>
            <RewardedVideoButton rewardType="prediction_points"/>
          </div>
        )}
      </aside>
    </div>
  );
};

export default PredictionsHub;
