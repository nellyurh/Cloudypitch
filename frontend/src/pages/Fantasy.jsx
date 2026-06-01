import React, { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { useAuth, formatApiErr } from "../lib/auth";
import { Link } from "react-router-dom";
import { ShieldCheck, Star, AlertTriangle, Check, X, Sparkles, Trophy, Crown, LogIn } from "lucide-react";
import CardPickerModal from "../components/CardPickerModal";
import { WcGamesPanel } from "./WcGames";

const POSITIONS = ["GK", "DEF", "MID", "FWD"];
const POS_LIMIT = { GK: 2, DEF: 5, MID: 5, FWD: 3 };
const POS_COLOR = { GK: "#FFC857", DEF: "#A3E635", MID: "#7DD3FC", FWD: "#FB7185" };

/** FPL-style jersey SVG — colour drives stroke + body fill. */
function Jersey({ color = "#A3E635", size = 40 }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden>
      <path
        d="M14 8 L24 4 C28 8 36 8 40 4 L50 8 L58 18 L50 24 L48 22 L48 56 C48 58 46 60 44 60 L20 60 C18 60 16 58 16 56 L16 22 L14 24 L6 18 Z"
        fill={color} stroke="rgba(0,0,0,0.35)" strokeWidth="1.6"
      />
      <path d="M16 30 L48 30" stroke="rgba(255,255,255,0.6)" strokeWidth="2"/>
    </svg>
  );
}

// FPL-style mini pitch — jersey + last name + (opponent) for each slot
function MiniPitch({ starters, players, captain, vice }) {
  const findMeta = (pid) => players.find(x => x.id === pid);
  const byPos = (pos) => starters.filter(s => s.position === pos).map(s => ({ ...s, meta: findMeta(s.player_id) }));
  const rows = [
    { pos: "GK", players: byPos("GK").slice(0, 1) },
    { pos: "DEF", players: byPos("DEF") },
    { pos: "MID", players: byPos("MID") },
    { pos: "FWD", players: byPos("FWD") },
  ];
  return (
    <div
      className="relative w-full rounded-lg overflow-hidden"
      style={{
        aspectRatio: "10 / 14",
        background: "repeating-linear-gradient(180deg, #0E6B3A 0 6%, #0A5A31 6% 12%)",
      }}
      data-testid="fantasy-pitch"
    >
      {/* Pitch markings */}
      <div className="absolute top-1/2 left-0 right-0 h-px bg-white/50" />
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 border border-white/50 rounded-full" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[60%] h-[16%] border-x border-b border-white/50" />
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[60%] h-[16%] border-x border-t border-white/50" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[30%] h-[7%] border-x border-b border-white/50" />
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[30%] h-[7%] border-x border-t border-white/50" />

      <div className="absolute inset-0 flex flex-col justify-around py-2">
        {rows.map(({ pos, players: ps }) => (
          <div key={pos} className="flex items-start justify-around gap-1 px-1">
            {ps.length === 0 ? (
              <span className="text-[10px]" style={{ color: "rgba(255,255,255,0.55)" }}>— add {pos} —</span>
            ) : ps.map(({ player_id, meta }) => {
              if (!meta) return null;
              const isCap = captain === player_id;
              const isVice = vice === player_id;
              const lastName = (meta.name || "?").split(" ").slice(-1)[0];
              return (
                <div key={player_id} className="flex flex-col items-center min-w-0 max-w-[90px] w-full" data-testid={`pitch-slot-${player_id}`}>
                  <div className="relative">
                    <Jersey color={POS_COLOR[pos]} size={38}/>
                    {isCap && (
                      <span className="absolute -top-1 -right-1 bg-cp-lime text-cp-forest text-[8px] font-extrabold w-4 h-4 rounded-full flex items-center justify-center ring-2 ring-black/40" data-testid="captain-badge">C</span>
                    )}
                    {isVice && (
                      <span className="absolute -top-1 -right-1 bg-white text-cp-forest text-[8px] font-extrabold w-4 h-4 rounded-full flex items-center justify-center ring-2 ring-black/40" data-testid="vice-badge">V</span>
                    )}
                  </div>
                  {/* Name + opponent stacked in white pill */}
                  <div className="mt-0.5 w-full max-w-[88px]">
                    <div className="text-[9px] font-extrabold leading-tight px-1 py-0.5 rounded-t truncate text-center"
                         style={{ background: "#FFFFFF", color: "#1A1F26" }}>
                      {lastName}
                    </div>
                    <div className="text-[8px] font-medium leading-tight px-1 py-0.5 rounded-b truncate text-center"
                         style={{ background: "#F1F4EF", color: "#475569" }}>
                      £{(meta.price || 0).toFixed(1)}m
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

export const FantasyHub = () => {
  const { user } = useAuth();
  const [tab, setTab] = useState("squad");
  const [comp, setComp] = useState(null);
  const [players, setPlayers] = useState([]);
  const [squad, setSquad] = useState({ name: "My WC Squad", players: [], captain: null, vice: null, appliedCards: [] });
  const [leaderboard, setLeaderboard] = useState([]);
  const [pool, setPool] = useState(null);
  const [filter, setFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("price"); // "price" | "name"
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [c, p, mine, lb] = await Promise.all([
          api.get("/fantasy/competition"),
          api.get("/fantasy/players?limit=2000"),
          user ? api.get("/fantasy/squad/me").catch(() => ({ data: { squad: null } })) : Promise.resolve({ data: { squad: null } }),
          api.get("/fantasy/leaderboard?limit=20").catch(() => ({ data: { leaderboard: [] } })),
        ]);
        setComp(c.data.competition);
        setPlayers(p.data.players || []);
        setLeaderboard(lb.data.leaderboard || []);
        if (lb.data.pool) setPool(lb.data.pool);
        if (mine.data.squad) {
          setSquad({
            name: mine.data.squad.squad_name || "My WC Squad",
            players: mine.data.squad.players || [],
            captain: mine.data.squad.captain_id,
            vice: mine.data.squad.vice_captain_id,
            appliedCards: mine.data.squad.applied_card_ids || [],
          });
        }
      } catch (_) {}
    })();
  }, [user]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    const arr = players.filter(p =>
      (filter === "ALL" || p.position === filter) &&
      (teamFilter === "ALL" || p.team_name === teamFilter) &&
      (!q || (p.name + " " + p.team_name).toLowerCase().includes(q))
    );
    if (sortBy === "price") arr.sort((a, b) => (b.price || 0) - (a.price || 0));
    else if (sortBy === "name") arr.sort((a, b) => a.name.localeCompare(b.name));
    return arr;
  }, [players, filter, teamFilter, search, sortBy]);

  const teamOptions = useMemo(() => {
    const set = new Set(players.map(p => p.team_name).filter(Boolean));
    return ["ALL", ...Array.from(set).sort()];
  }, [players]);

  const totalCost = useMemo(() => squad.players.reduce((s, p) => s + (Number(p.price_paid) || 0), 0), [squad.players]);
  const counts = useMemo(() => squad.players.reduce((acc, p) => { acc[p.position] = (acc[p.position] || 0) + 1; return acc; }, {}), [squad.players]);
  const starters = useMemo(() => squad.players.filter(p => p.is_starting).slice(0, 11), [squad.players]);
  const budget = comp?.budget_total || 100;
  const squadSize = comp?.squad_size || 15;
  const overBudget = totalCost > budget;
  const overSize = squad.players.length > squadSize;

  const togglePlayer = (p) => {
    setSquad(s => {
      const has = s.players.find(x => x.player_id === p.id);
      if (has) return { ...s, players: s.players.filter(x => x.player_id !== p.id), captain: s.captain === p.id ? null : s.captain, vice: s.vice === p.id ? null : s.vice };
      if (s.players.length >= squadSize) return s;
      if ((counts[p.position] || 0) >= POS_LIMIT[p.position]) return s;
      return { ...s, players: [...s.players, { player_id: p.id, position: p.position, is_starting: s.players.length < 11, price_paid: p.price }] };
    });
  };

  const setVice = (pid) => setSquad(s => ({ ...s, vice: s.vice === pid ? null : pid }));

  const save = async () => {
    if (!user) return;
    setErr("");
    try {
      await api.post("/fantasy/squad", {
        competition_id: comp.id, squad_name: squad.name,
        captain_id: squad.captain, vice_captain_id: squad.vice,
        players: squad.players,
        applied_card_ids: squad.appliedCards || [],
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) { setErr(formatApiErr(e)); }
  };

  const budgetPct = Math.min(100, (totalCost / budget) * 100);

  // Sign-in gate for full Fantasy
  if (!user) {
    return (
      <div className="cp-surface p-10 text-center max-w-xl mx-auto mt-6" data-testid="fantasy-signin-gate">
        <Trophy size={36} className="mx-auto text-cp-lime"/>
        <h1 className="text-2xl font-extrabold mt-3">Build your WC 2026 Fantasy Squad</h1>
        <p className="text-sm mt-2" style={{ color: "var(--cp-text-muted)" }}>
          Sign in to pick 15 players, captain your stars, play 148 mini-games, apply Legend Card boosts, and chase the $30,000 prize pool.
        </p>
        <div className="flex gap-2 mt-5 justify-center">
          <Link to="/signin" className="cp-btn-primary inline-flex items-center gap-1" data-testid="fantasy-go-signin"><LogIn size={14}/> Sign in</Link>
          <Link to="/signup" className="cp-btn-ghost" data-testid="fantasy-go-signup">Create free account</Link>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="fantasy-hub">
      <div className="cp-surface p-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>FIFA WC 2026 · Fantasy</div>
          <h1 className="text-xl font-extrabold mt-0.5">{comp?.name || "Build Your Squad"}</h1>
          <p className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>
            1 tournament-long squad · 148 mini-games · Legend Card boosts apply here
          </p>
        </div>
      </div>

      <div className="flex gap-1 cp-surface p-1 mt-3 w-fit">
        {[
          { k: "squad", l: "My Squad" },
          { k: "games", l: "WC Games (148)" },
          { k: "leaderboard", l: "Leaderboard" },
        ].map(t => (
          <button
            key={t.k}
            onClick={() => setTab(t.k)}
            className={`px-3 py-1.5 text-sm rounded ${tab === t.k ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`}
            data-testid={`fantasy-tab-${t.k}`}
          >
            {t.l}
          </button>
        ))}
      </div>

      {tab === "games" && <div className="mt-3"><WcGamesPanel user={user}/></div>}

      {tab === "leaderboard" && (
        <div className="space-y-3 mt-3" data-testid="fantasy-leaderboard">
          {pool && (
            <div className="cp-surface p-4 text-center" data-testid="leaderboard-pool">
              <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Total Prize Pool</div>
              <div className="text-3xl font-extrabold text-cp-lime mt-1">${((pool.total_usd_cents || 0) / 100).toLocaleString()}</div>
              <div className="text-[11px] mt-1" style={{ color: "var(--cp-text-muted)" }}>
                ${((pool.base_usd_cents || 0) / 100).toLocaleString()} base + ${((pool.cards_cut_usd_cents || 0) / 100).toLocaleString()} cards cut (50% of card spend)
              </div>
              <div className="grid grid-cols-4 gap-2 mt-3 text-[10px]">
                {[{ p: 1, l: "🥇" }, { p: 2, l: "🥈" }, { p: 3, l: "🥉" }, { p: 4, l: "4️⃣" }].map(x => (
                  <div key={x.p} className="cp-surface !bg-transparent ring-1 ring-white/10 p-2 rounded">
                    <div>{x.l}</div>
                    <div className="text-cp-lime font-bold tabular-nums">{[1000, 500, 300, 200][x.p - 1]}$</div>
                  </div>
                ))}
              </div>
              <div className="text-[10px] mt-2" style={{ color: "var(--cp-text-muted)" }}>
                Pos 5–20 share ${((pool.base_usd_cents - 180000) / 100).toFixed(0)} equally · Pos 21+ earns from cards cut
              </div>
            </div>
          )}
          <div className="cp-surface overflow-hidden">
            <div className="cp-card-header normal-case"><span className="font-bold flex items-center gap-2"><Crown size={14} className="text-cp-lime"/> Unified Leaderboard · Fantasy + Predictions</span></div>
            <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
              {leaderboard.length === 0 && <li className="p-4 text-sm" style={{ color: "var(--cp-text-muted)" }}>No scores yet — be first!</li>}
              {leaderboard.map(r => (
                <li key={r.user_id} className={`px-3 py-2 flex items-center gap-2 text-sm ${r.user_id === user.id ? "bg-cp-lime/10" : ""}`}>
                  <span className="cp-logo-circle text-[10px] font-extrabold" style={{ width: 22, height: 22, background: r.rank === 1 ? "#A3E635" : r.rank <= 4 ? "rgba(163,230,53,0.4)" : "var(--cp-surface-2)", color: r.rank === 1 ? "#064E3B" : "var(--cp-text)" }}>{r.rank}</span>
                  <span className="truncate flex-1">{r.display_name}</span>
                  <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>F {r.fantasy_points} · P {r.prediction_points}</span>
                  {r.potential_prize_usd_cents > 0 && (
                    <span className="text-[11px] tabular-nums font-bold" style={{ color: "#A3E635" }}>${(r.potential_prize_usd_cents / 100).toFixed(0)}</span>
                  )}
                  <span className="tabular-nums font-bold text-cp-lime">{r.total_points}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {tab === "squad" && <>
      <div className="flex items-center justify-end gap-2 mt-3">
        <button
          onClick={() => setPickerOpen(true)}
          className={`cp-pill text-xs font-bold inline-flex items-center gap-1 ${(squad.appliedCards || []).length > 0 ? "ring-1 ring-cp-lime" : ""}`}
          style={{ background: (squad.appliedCards || []).length > 0 ? "rgba(163,230,53,0.15)" : "var(--cp-surface-2)", color: (squad.appliedCards || []).length > 0 ? "#A3E635" : "var(--cp-text-muted)" }}
          data-testid="fantasy-boost-btn"
        >
          <Sparkles size={12}/> {(squad.appliedCards || []).length > 0 ? `${(squad.appliedCards || []).length} cards applied` : "Apply boost cards"}
        </button>
        <button
          onClick={save}
          disabled={overBudget || overSize || squad.players.length === 0}
          className="cp-btn-primary disabled:opacity-50 inline-flex items-center gap-1"
          data-testid="fantasy-save-btn"
        >
          {saved ? <><Check size={14}/> Saved</> : "Save Squad"}
        </button>
      </div>

      {/* Squad Stats Bar */}
      <div className="cp-surface p-3 mt-3 grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="fantasy-stats">
        <div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Squad</div>
          <div className="text-xl font-extrabold tabular-nums">{squad.players.length}<span className="text-sm font-normal" style={{ color: "var(--cp-text-muted)" }}>/{squadSize}</span></div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Starters</div>
          <div className="text-xl font-extrabold tabular-nums">{starters.length}<span className="text-sm font-normal" style={{ color: "var(--cp-text-muted)" }}>/11</span></div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Bank</div>
          <div className={`text-xl font-extrabold tabular-nums ${overBudget ? "text-rose-400" : "text-cp-lime"}`}>£{Math.max(0, budget - totalCost).toFixed(1)}m</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Spent</div>
          <div className="text-xl font-extrabold tabular-nums">£{totalCost.toFixed(1)}m</div>
          <div className="h-1 rounded mt-1" style={{ background: "var(--cp-surface-2)" }}>
            <div className={`h-1 rounded transition-all ${overBudget ? "bg-rose-500" : "bg-cp-lime"}`} style={{ width: `${budgetPct}%` }}/>
          </div>
        </div>
      </div>

      {(err || overBudget || overSize) && (
        <div className="cp-surface p-3 text-sm mt-3 flex items-center gap-2" style={{ borderColor: "#FF3D52", color: "#FF3D52" }}>
          <AlertTriangle size={14}/>
          {err || (overBudget ? `Over budget: £${totalCost.toFixed(1)}m / £${budget}m` : `Squad too large: ${squad.players.length} / ${squadSize}`)}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 mt-3">
        <section>
          <div className="flex items-center gap-2 mb-2">
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search players or teams…" className="cp-input flex-1" data-testid="fantasy-search"/>
            <select
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
              className="cp-input text-xs max-w-[140px]"
              data-testid="team-filter"
            >
              {teamOptions.map(t => <option key={t} value={t}>{t === "ALL" ? "All teams" : t}</option>)}
            </select>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="cp-input text-xs max-w-[110px]"
              data-testid="sort-by"
            >
              <option value="price">£ High → Low</option>
              <option value="name">Name A–Z</option>
            </select>
            <div className="flex gap-1 cp-surface p-1">
              {["ALL", ...POSITIONS].map(p => (
                <button key={p} onClick={() => setFilter(p)} className={`px-2.5 py-1 rounded text-xs font-bold ${filter === p ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`} data-testid={`pos-filter-${p}`}>{p}</button>
              ))}
            </div>
          </div>
          <div className="cp-surface overflow-hidden divide-y max-h-[70vh] overflow-y-auto scrollbar-thin" style={{ borderColor: "var(--cp-border)" }}>
            {filtered.slice(0, 200).map(p => {
              const inSquad = squad.players.find(x => x.player_id === p.id);
              const posFull = (counts[p.position] || 0) >= POS_LIMIT[p.position] && !inSquad;
              return (
                <button
                  key={p.id}
                  onClick={() => togglePlayer(p)}
                  disabled={!inSquad && (squad.players.length >= squadSize || posFull)}
                  className="w-full px-3 py-2 flex items-center gap-3 text-sm hover:bg-white/5 text-left disabled:opacity-40"
                  data-testid={`player-${p.id}`}
                >
                  {p.team_logo ? (
                    <img src={p.team_logo} className="w-6 h-6 object-contain shrink-0" alt="" onError={(e)=>{e.target.style.display="none"}}/>
                  ) : (
                    <span className="w-6 h-6 rounded-sm shrink-0" style={{ background: "var(--cp-surface-2)" }}/>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="truncate font-medium">{p.name}</div>
                    <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{p.team_name}</div>
                  </div>
                  <span
                    className="cp-pill text-[10px] font-bold"
                    style={{ background: POS_COLOR[p.position] + "22", color: POS_COLOR[p.position] }}
                  >
                    {p.position}
                  </span>
                  <span className="cp-pill tabular-nums" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text)" }}>£{(p.price || 5).toFixed(1)}m</span>
                  {inSquad && <Check size={14} className="text-cp-lime"/>}
                </button>
              );
            })}
          </div>
        </section>

        <aside className="space-y-3 h-fit lg:sticky lg:top-[110px]">
          <div className="cp-surface overflow-hidden">
            <div className="cp-card-header normal-case">
              <span className="flex items-center gap-2 font-bold" style={{ color: "var(--cp-text)" }}><ShieldCheck size={14} className="text-cp-lime"/> Starting XI</span>
              <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{starters.length}/11</span>
            </div>
            <div className="p-2">
              <MiniPitch starters={starters} players={players} captain={squad.captain} vice={squad.vice}/>
            </div>
          </div>

          <div className="cp-surface overflow-hidden">
            <div className="cp-card-header normal-case">
              <span className="flex items-center gap-2 font-bold" style={{ color: "var(--cp-text)" }}>Squad List</span>
              <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{squad.players.length}/{squadSize}</span>
            </div>
            {POSITIONS.map(pos => (
              <div key={pos} className="p-2 border-b" style={{ borderColor: "var(--cp-border)" }}>
                <div className="text-[10px] uppercase tracking-widest mb-1 flex items-center justify-between">
                  <span style={{ color: POS_COLOR[pos] }}>{pos}</span>
                  <span style={{ color: "var(--cp-text-muted)" }}>{counts[pos] || 0}/{POS_LIMIT[pos]}</span>
                </div>
                <ul className="space-y-1">
                  {squad.players.filter(p => p.position === pos).map(p => {
                    const meta = players.find(x => x.id === p.player_id);
                    if (!meta) return null;
                    return (
                      <li key={p.player_id} className="flex items-center gap-2 text-sm">
                        <span className="flex-1 truncate">{meta.name}</span>
                        <button
                          onClick={() => setSquad(s => ({ ...s, captain: s.captain === p.player_id ? null : p.player_id }))}
                          className={`p-1 rounded ${squad.captain === p.player_id ? "text-cp-lime" : "opacity-50 hover:opacity-100"}`}
                          title="Captain (×2 points)"
                          data-testid={`captain-${p.player_id}`}
                        >
                          <Star size={12} fill={squad.captain === p.player_id ? "#A3E635" : "transparent"}/>
                        </button>
                        <button
                          onClick={() => setVice(p.player_id)}
                          className={`p-1 rounded text-[10px] font-bold ${squad.vice === p.player_id ? "text-white bg-white/20" : "opacity-50 hover:opacity-100"}`}
                          title="Vice-captain"
                          data-testid={`vice-${p.player_id}`}
                        >
                          V
                        </button>
                        <span className="text-[10px] tabular-nums" style={{ color: "var(--cp-text-muted)" }}>£{p.price_paid?.toFixed?.(1) || meta.price?.toFixed?.(1) || "5.0"}m</span>
                        <button onClick={() => togglePlayer(meta)} className="p-1 opacity-50 hover:opacity-100 hover:text-rose-400" title="Remove" data-testid={`remove-${p.player_id}`}>
                          <X size={12}/>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        </aside>
      </div>
      </>}

      {pickerOpen && (
        <CardPickerModal
          match={null}
          basePoints={50}
          stageMult={1.0}
          selectedIds={squad.appliedCards || []}
          maxCards={5}
          onSave={(ids) => setSquad(s => ({ ...s, appliedCards: ids }))}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </div>
  );
};

export default FantasyHub;
