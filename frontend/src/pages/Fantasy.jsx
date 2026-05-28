import React, { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { useAuth, formatApiErr } from "../lib/auth";
import { Link } from "react-router-dom";
import { ShieldCheck, Star, AlertTriangle, Check, X } from "lucide-react";

const POSITIONS = ["GK", "DEF", "MID", "FWD"];
const POS_LIMIT = { GK: 2, DEF: 5, MID: 5, FWD: 3 };
const POS_COLOR = { GK: "#FFC857", DEF: "#A3E635", MID: "#7DD3FC", FWD: "#FB7185" };

// Mini pitch with starting 11 placement
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
        background: "repeating-linear-gradient(180deg, #0e6b3a 0 6%, #0a5a31 6% 12%)",
      }}
      data-testid="fantasy-pitch"
    >
      <div className="absolute top-1/2 left-0 right-0 h-px bg-white/50" />
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-14 h-14 border border-white/50 rounded-full" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[55%] h-[14%] border-x border-b border-white/50" />
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[55%] h-[14%] border-x border-t border-white/50" />

      <div className="absolute inset-0 flex flex-col justify-around py-3">
        {rows.map(({ pos, players: ps }) => (
          <div key={pos} className="flex items-center justify-center gap-1 px-2">
            {ps.length === 0 ? (
              <span className="text-[10px]" style={{ color: "rgba(255,255,255,0.5)" }}>—</span>
            ) : ps.map(({ player_id, meta }) => {
              if (!meta) return null;
              const isCap = captain === player_id;
              const isVice = vice === player_id;
              return (
                <div key={player_id} className="flex flex-col items-center min-w-0 max-w-[80px]">
                  <div className="relative">
                    <div
                      className="w-9 h-9 rounded-full flex items-center justify-center text-[10px] font-extrabold text-cp-forest shadow ring-2 ring-black/40"
                      style={{ background: POS_COLOR[pos] }}
                    >
                      {(meta.name || "?").split(" ").slice(-1)[0].slice(0, 3).toUpperCase()}
                    </div>
                    {isCap && (
                      <span className="absolute -top-1 -right-1 bg-cp-lime text-cp-forest text-[8px] font-extrabold w-4 h-4 rounded-full flex items-center justify-center ring-2 ring-black/40">C</span>
                    )}
                    {isVice && (
                      <span className="absolute -top-1 -right-1 bg-white text-cp-forest text-[8px] font-extrabold w-4 h-4 rounded-full flex items-center justify-center ring-2 ring-black/40">V</span>
                    )}
                  </div>
                  <div className="mt-0.5 text-[9px] font-medium px-1 leading-tight max-w-full truncate text-center" style={{ background: "rgba(0,0,0,0.55)", color: "#fff" }}>
                    {(meta.name || "?").split(" ").slice(-1)[0]}
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
  const [comp, setComp] = useState(null);
  const [players, setPlayers] = useState([]);
  const [squad, setSquad] = useState({ name: "My WC Squad", players: [], captain: null, vice: null });
  const [filter, setFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [c, p, mine] = await Promise.all([
          api.get("/fantasy/competition"),
          api.get("/fantasy/players?limit=300"),
          user ? api.get("/fantasy/squad/me").catch(() => ({ data: { squad: null } })) : Promise.resolve({ data: { squad: null } }),
        ]);
        setComp(c.data.competition);
        setPlayers(p.data.players || []);
        if (mine.data.squad) {
          setSquad({
            name: mine.data.squad.squad_name || "My WC Squad",
            players: mine.data.squad.players || [],
            captain: mine.data.squad.captain_id,
            vice: mine.data.squad.vice_captain_id,
          });
        }
      } catch (_) {}
    })();
  }, [user]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return players.filter(p => (filter === "ALL" || p.position === filter) && (!q || (p.name + " " + p.team_name).toLowerCase().includes(q)));
  }, [players, filter, search]);

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
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) { setErr(formatApiErr(e)); }
  };

  const budgetPct = Math.min(100, (totalCost / budget) * 100);

  return (
    <div data-testid="fantasy-hub">
      <div className="cp-surface p-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>FIFA WC 2026 · Fantasy</div>
          <h1 className="text-xl font-extrabold mt-0.5">{comp?.name || "Build Your Squad"}</h1>
          <p className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>
            {squadSize} players · Budget £{budget}m · {comp?.transfers_per_gw || 1} transfer/GW · GK starts × 2pts · Goals 4-6pts · Captain × 2
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!user && <Link to="/signin" className="cp-btn-primary" data-testid="fantasy-signin-cta">Sign in to save</Link>}
          {user && (
            <button
              onClick={save}
              disabled={overBudget || overSize || squad.players.length === 0}
              className="cp-btn-primary disabled:opacity-50 inline-flex items-center gap-1"
              data-testid="fantasy-save-btn"
            >
              {saved ? <><Check size={14}/> Saved</> : "Save Squad"}
            </button>
          )}
        </div>
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
    </div>
  );
};

export default FantasyHub;
