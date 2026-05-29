import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth, formatApiErr } from "../lib/auth";
import { Trophy, Clock, Users, Sparkles, Lock, Check, AlertTriangle } from "lucide-react";

const POSITIONS = ["GK", "DEF", "MID", "FWD"];
const POS_COLOR = { GK: "#FFC857", DEF: "#A3E635", MID: "#7DD3FC", FWD: "#FB7185" };
const TYPE_LABEL = { match: "Match Game", group: "Group Game", round: "Round Game" };
const STAGE_LABEL = {
  any: "Match",
  group_md1: "Group · MD1", group_md2: "Group · MD2", group_md3: "Group · MD3",
  r32: "Round of 32", r16: "Round of 16", qf: "Quarterfinals", sf: "Semifinals", finals: "Finals",
};

function timeToOpenOrClose(g) {
  const now = Date.now();
  const opens = new Date(g.opens_at).getTime();
  const closes = new Date(g.closes_at).getTime();
  if (now < opens) return { label: "Opens", at: g.opens_at };
  if (now < closes) return { label: "Closes", at: g.closes_at };
  return { label: "Closed", at: g.closes_at };
}

function GameCard({ g, onOpen }) {
  const t = timeToOpenOrClose(g);
  const entered = !!g.my_entry;
  return (
    <button
      onClick={() => onOpen(g)}
      className="cp-surface p-3 text-left w-full hover:bg-white/5 transition flex flex-col gap-2"
      data-testid={`wc-game-${g.id}`}
    >
      <div className="flex items-center justify-between">
        <span className="cp-pill text-[10px] font-bold" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text)" }}>
          {TYPE_LABEL[g.game_type]}
        </span>
        <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>
          {STAGE_LABEL[g.stage] || g.stage}
        </span>
      </div>
      <div className="text-sm font-bold leading-tight">
        {g.game_type === "group" ? `Group ${g.group_letter} · MD${g.matchday}` : g.game_type === "round" ? `${STAGE_LABEL[g.stage] || g.stage} – tournament-wide` : "Single match"}
      </div>
      <div className="flex items-center gap-3 text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
        <span className="inline-flex items-center gap-1"><Clock size={11}/>{t.label} {new Date(t.at).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
        <span className="inline-flex items-center gap-1"><Users size={11}/>{g.total_entries || 0}</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
          {(g.eligible_team_ids || []).length} teams · {g.card_limit_current ?? 2} cards · ×{g.points_multiplier || 1.0}
        </span>
        {entered ? (
          <span className="cp-pill text-[10px] font-bold inline-flex items-center gap-1" style={{ background: "rgba(163,230,53,0.15)", color: "#A3E635" }}>
            <Check size={10}/> Entered
          </span>
        ) : g.status === "open" ? (
          <span className="cp-pill text-[10px] font-bold" style={{ background: "rgba(163,230,53,0.15)", color: "#A3E635" }}>Play now</span>
        ) : g.status === "upcoming" ? (
          <span className="cp-pill text-[10px] font-bold" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>Soon</span>
        ) : (
          <span className="cp-pill text-[10px] font-bold inline-flex items-center gap-1" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}><Lock size={10}/>Closed</span>
        )}
      </div>
    </button>
  );
}

function GameEntryView({ game, onClose, onSaved }) {
  const [details, setDetails] = useState(null);
  const [picks, setPicks] = useState({}); // { player_id: { position, team_id } }
  const [captain, setCaptain] = useState(null);
  const [vice, setVice] = useState(null);
  // appliedCards: array of { user_card_id, target_player_id }
  const [appliedCards, setAppliedCards] = useState([]);
  const [ownedCards, setOwnedCards] = useState([]);
  const [targetingCard, setTargetingCard] = useState(null); // user_card_id currently being targeted
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/wc/games/${game.id}`);
        setDetails(data.game);
        if (data.game.my_entry) {
          const seed = {};
          for (const p of data.game.my_entry.player_picks || []) {
            seed[p.player_id] = { position: p.position, team_id: p.team_id };
          }
          setPicks(seed);
          setCaptain(data.game.my_entry.captain_player_id);
          setVice(data.game.my_entry.vice_captain_player_id);
          setAppliedCards((data.game.my_entry.cards_used || []).map(c => ({
            user_card_id: c.user_card_id, target_player_id: c.target_player_id || null,
          })));
        }
      } catch (e) { setErr(formatApiErr(e)); }
      try {
        const { data } = await api.get("/cards/me");
        setOwnedCards((data.owned || []).filter(o => (o.uses_remaining || o.uses_left || 0) > 0));
      } catch (_) {}
    })();
  }, [game.id]);

  const totalPicks = Object.keys(picks).length;
  const cardCap = details?.card_limit_current ?? game.card_limit_current ?? 2;

  const togglePick = (p) => {
    setPicks(prev => {
      const next = { ...prev };
      if (next[p.id]) {
        delete next[p.id];
        if (captain === p.id) setCaptain(null);
        if (vice === p.id) setVice(null);
        // Remove any card targeting this player
        setAppliedCards(ac => ac.filter(c => c.target_player_id !== p.id));
      } else {
        if (Object.keys(prev).length >= 11) return prev;
        next[p.id] = { position: p.position, team_id: p.team_id };
      }
      return next;
    });
  };

  const toggleCard = (uc) => {
    setAppliedCards(prev => {
      const exists = prev.find(c => c.user_card_id === uc.id);
      if (exists) return prev.filter(c => c.user_card_id !== uc.id);
      if (prev.length >= cardCap) return prev;
      // New card — must immediately target a player; open targeting picker
      setTargetingCard(uc.id);
      return [...prev, { user_card_id: uc.id, target_player_id: null }];
    });
  };

  const targetCardToPlayer = (user_card_id, target_player_id) => {
    setAppliedCards(prev => prev.map(c => c.user_card_id === user_card_id ? { ...c, target_player_id } : c));
    setTargetingCard(null);
  };

  const submit = async () => {
    if (totalPicks !== 11) return setErr("Pick exactly 11 players");
    if (appliedCards.some(c => !c.target_player_id)) return setErr("Each applied card must target a player");
    setBusy(true); setErr("");
    try {
      await api.post(`/wc/games/${game.id}/enter`, {
        player_picks: Object.entries(picks).map(([player_id, meta]) => ({ player_id, position: meta.position, team_id: meta.team_id })),
        captain_player_id: captain, vice_captain_player_id: vice,
        cards_used: appliedCards.map(c => ({ user_card_id: c.user_card_id, target_player_id: c.target_player_id })),
      });
      onSaved?.();
      onClose?.();
    } catch (e) { setErr(formatApiErr(e)); }
    setBusy(false);
  };

  if (!details) return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center p-3" style={{ background: "rgba(0,0,0,0.7)" }}>
      <div className="cp-surface p-6">Loading game…</div>
    </div>
  );

  const eligible = details.eligible_players || [];
  const grouped = POSITIONS.map(pos => ({ pos, players: eligible.filter(p => p.position === pos) }));

  return (
    <div className="fixed inset-0 z-[150] flex items-end md:items-center justify-center p-2 md:p-4" style={{ background: "rgba(0,0,0,0.7)" }} data-testid="wc-game-entry">
      <div className="cp-surface w-full max-w-3xl max-h-[92vh] overflow-hidden flex flex-col relative">
        <div className="px-4 py-3 flex items-center justify-between border-b" style={{ borderColor: "var(--cp-border)" }}>
          <div>
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{TYPE_LABEL[game.game_type]} · {STAGE_LABEL[game.stage] || game.stage}</div>
            <div className="text-base font-extrabold">Pick 11 · {cardCap} cards · ×{details.points_multiplier || 1.0}</div>
          </div>
          <button onClick={onClose} className="cp-btn-ghost !p-2" data-testid="wc-close">✕</button>
        </div>

        <div className="px-4 py-2 grid grid-cols-3 text-center text-xs gap-2 border-b" style={{ borderColor: "var(--cp-border)" }}>
          <div><span className="font-bold tabular-nums" style={{ color: totalPicks === 11 ? "#A3E635" : "var(--cp-text)" }}>{totalPicks}</span>/11 picked</div>
          <div><span className="font-bold tabular-nums">{appliedCards.length}</span>/{cardCap} cards</div>
          <div className="text-cp-lime">Captain ×2</div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {err && <div className="text-xs" style={{ color: "#FF3D52" }}><AlertTriangle size={12} className="inline mr-1"/>{err}</div>}
          {grouped.map(({ pos, players }) => (
            <section key={pos}>
              <h4 className="text-[10px] uppercase tracking-widest mb-1" style={{ color: POS_COLOR[pos] }}>{pos} · {players.length}</h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5">
                {players.slice(0, 90).map(p => {
                  const sel = !!picks[p.id];
                  return (
                    <button
                      key={p.id}
                      onClick={() => togglePick(p)}
                      disabled={!sel && totalPicks >= 11}
                      className={`px-2 py-1.5 rounded text-xs text-left flex items-center gap-1.5 disabled:opacity-30 ${sel ? "ring-1 ring-cp-lime bg-cp-lime/10" : "hover:bg-white/5"}`}
                      style={{ background: sel ? undefined : "var(--cp-surface-2)" }}
                      data-testid={`wc-pick-${p.id}`}
                    >
                      {p.team_logo && <img src={p.team_logo} className="w-4 h-4 object-contain shrink-0" alt="" onError={(e)=>{e.target.style.display="none"}}/>}
                      <span className="truncate flex-1">{p.name}</span>
                      {sel && (
                        <>
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); setCaptain(c => c === p.id ? null : p.id); if (vice === p.id) setVice(null); }}
                            className={`text-[8px] font-extrabold w-4 h-4 rounded ${captain === p.id ? "bg-cp-lime text-cp-forest" : "border border-current opacity-60"}`}
                            data-testid={`wc-cap-${p.id}`}
                          >C</button>
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); setVice(v => v === p.id ? null : p.id); if (captain === p.id) setCaptain(null); }}
                            className={`text-[8px] font-extrabold w-4 h-4 rounded ${vice === p.id ? "bg-white text-cp-forest" : "border border-current opacity-60"}`}
                            data-testid={`wc-vice-${p.id}`}
                          >V</button>
                        </>
                      )}
                    </button>
                  );
                })}
              </div>
            </section>
          ))}

          {ownedCards.length > 0 && (
            <section>
              <h4 className="text-[10px] uppercase tracking-widest mb-1 inline-flex items-center gap-1"><Sparkles size={10} className="text-cp-lime"/>Boost Cards · {appliedCards.length}/{cardCap}</h4>
              <p className="text-[10px] mb-1.5" style={{ color: "var(--cp-text-muted)" }}>Each card boosts ONE picked player. 1 use per card per game — consumed on submit.</p>
              <div className="grid grid-cols-2 gap-1.5">
                {ownedCards.map(uc => {
                  const applied = appliedCards.find(c => c.user_card_id === uc.id);
                  const sel = !!applied;
                  const targetedPlayer = applied?.target_player_id ? eligible.find(p => p.id === applied.target_player_id) : null;
                  return (
                    <div key={uc.id} className={`rounded text-xs ${sel ? "ring-1 ring-cp-lime bg-cp-lime/10" : ""}`} style={{ background: sel ? undefined : "var(--cp-surface-2)" }}>
                      <button
                        onClick={() => toggleCard(uc)}
                        disabled={!sel && appliedCards.length >= cardCap}
                        className="px-2 py-1.5 w-full text-left disabled:opacity-30"
                        data-testid={`wc-card-${uc.id}`}
                      >
                        <div className="font-bold truncate">{uc.card?.name}</div>
                        <div className="text-[10px] opacity-70">+{Math.round(((uc.card?.effect_value?.multiplier || 1) - 1) * 100)}% · {uc.uses_remaining ?? uc.uses_left} uses left</div>
                      </button>
                      {sel && (
                        <button
                          onClick={() => setTargetingCard(uc.id)}
                          className="w-full px-2 py-1 text-[10px] border-t inline-flex items-center justify-between gap-1"
                          style={{ borderColor: "var(--cp-border)", color: targetedPlayer ? "#A3E635" : "#FBBF24" }}
                          data-testid={`wc-card-target-${uc.id}`}
                        >
                          <span>{targetedPlayer ? `→ ${targetedPlayer.name}` : "→ Pick target player"}</span>
                          <span>change</span>
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </div>

        <div className="px-4 py-3 flex gap-2 border-t" style={{ borderColor: "var(--cp-border)" }}>
          <button onClick={onClose} className="cp-btn-ghost flex-1" data-testid="wc-cancel">Cancel</button>
          <button onClick={submit} disabled={busy || totalPicks !== 11} className="cp-btn-primary flex-1 disabled:opacity-50" data-testid="wc-submit">
            {busy ? "Saving…" : `Submit ${totalPicks}/11`}
          </button>
        </div>

        {targetingCard && (
          <div className="absolute inset-0 z-[10] flex items-center justify-center p-3" style={{ background: "rgba(0,0,0,0.85)" }} data-testid="wc-target-picker">
            <div className="cp-surface w-full max-w-md max-h-[80vh] overflow-hidden flex flex-col">
              <div className="px-4 py-3 flex items-center justify-between border-b" style={{ borderColor: "var(--cp-border)" }}>
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-cp-lime">Boost target</div>
                  <div className="text-sm font-extrabold">{ownedCards.find(o => o.id === targetingCard)?.card?.name || "Card"}</div>
                </div>
                <button onClick={() => { setAppliedCards(ac => ac.filter(c => c.user_card_id !== targetingCard)); setTargetingCard(null); }} className="cp-btn-ghost !p-2" data-testid="wc-target-cancel">✕</button>
              </div>
              <div className="overflow-y-auto p-2">
                {Object.keys(picks).length === 0 && (
                  <div className="p-4 text-xs text-center" style={{ color: "var(--cp-text-muted)" }}>Pick players first, then apply cards to them.</div>
                )}
                {Object.keys(picks).map(pid => {
                  const p = eligible.find(x => x.id === pid);
                  if (!p) return null;
                  // Disable if another applied card already targets this player
                  const usedByOther = appliedCards.find(c => c.target_player_id === pid && c.user_card_id !== targetingCard);
                  return (
                    <button
                      key={pid}
                      onClick={() => !usedByOther && targetCardToPlayer(targetingCard, pid)}
                      disabled={!!usedByOther}
                      className="w-full px-2 py-1.5 text-left text-sm rounded hover:bg-white/5 disabled:opacity-30 flex items-center gap-2"
                      data-testid={`wc-target-pick-${pid}`}
                    >
                      {p.team_logo && <img src={p.team_logo} className="w-4 h-4 object-contain" alt="" onError={(e)=>{e.target.style.display="none"}}/>}
                      <span className="cp-pill text-[9px] font-bold" style={{ background: "var(--cp-surface-2)", color: POS_COLOR[p.position] }}>{p.position}</span>
                      <span className="flex-1 truncate">{p.name}</span>
                      {usedByOther && <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>boosted</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export const WcGamesPanel = ({ user }) => {
  const [today, setToday] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [tab, setTab] = useState("open");
  const [active, setActive] = useState(null);
  const [tick, setTick] = useState(0);

  const load = async () => {
    try {
      const [t, u] = await Promise.all([api.get("/wc/games/today"), api.get("/wc/games/upcoming?limit=80")]);
      setToday(t.data.games || []);
      setUpcoming(u.data.games || []);
    } catch (_) {}
  };

  useEffect(() => { load(); }, [tick]);

  const list = tab === "open" ? today : upcoming;
  const empty = list.length === 0;

  return (
    <div data-testid="wc-games-panel">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
        <div>
          <div className="text-xs" style={{ color: "var(--cp-text-muted)" }}>104 Match · 36 Group · 8 Round · 148 short-form games over the tournament</div>
        </div>
        <div className="flex gap-1 cp-surface p-1">
          <button onClick={() => setTab("open")} className={`px-3 py-1.5 text-sm rounded ${tab === "open" ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid="wc-tab-open">Open ({today.length})</button>
          <button onClick={() => setTab("upcoming")} className={`px-3 py-1.5 text-sm rounded ${tab === "upcoming" ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid="wc-tab-upcoming">Upcoming ({upcoming.length})</button>
        </div>
      </div>

      {empty ? (
        <div className="cp-surface p-8 text-center" data-testid="wc-empty">
          <Trophy size={36} className="mx-auto text-cp-lime opacity-60"/>
          <h3 className="text-base font-bold mt-3">No games {tab === "open" ? "open" : "scheduled"} yet</h3>
          <p className="text-xs mt-1 max-w-md mx-auto" style={{ color: "var(--cp-text-muted)" }}>
            Match Games open 7 days before kickoff, Group Games 24h before, Round Games 48h before. Check back as June 11, 2026 approaches.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {list.map(g => <GameCard key={g.id} g={g} onOpen={(game) => setActive(game)}/>)}
        </div>
      )}

      {active && user && (
        <GameEntryView game={active} onClose={() => setActive(null)} onSaved={() => setTick(t => t + 1)}/>
      )}
    </div>
  );
};

export const WcGames = () => {
  const { user } = useAuth();
  return (
    <div data-testid="wc-games-page">
      <div className="cp-surface p-4 mb-3">
        <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>FIFA WC 2026 · 148 Fantasy Games</div>
        <h1 className="text-xl font-extrabold tracking-tight mt-0.5">Pick 11. Apply Boosts. Win Big.</h1>
      </div>
      <WcGamesPanel user={user}/>
    </div>
  );
};

export default WcGames;
