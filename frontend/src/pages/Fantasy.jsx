import React, { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { useAuth, formatApiErr } from "../lib/auth";
import { Link } from "react-router-dom";
import { ShieldCheck, Star, Coins, AlertTriangle, Check } from "lucide-react";

const POSITIONS = ["GK", "DEF", "MID", "FWD"];
const POS_LIMIT = { GK: 2, DEF: 5, MID: 5, FWD: 3 };

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
  const budget = comp?.budget_total || 100;
  const overBudget = totalCost > budget;
  const overSize = squad.players.length > (comp?.squad_size || 15);

  const togglePlayer = (p) => {
    setSquad(s => {
      const has = s.players.find(x => x.player_id === p.id);
      if (has) return { ...s, players: s.players.filter(x => x.player_id !== p.id), captain: s.captain === p.id ? null : s.captain, vice: s.vice === p.id ? null : s.vice };
      if (s.players.length >= (comp?.squad_size || 15)) return s;
      if ((counts[p.position] || 0) >= POS_LIMIT[p.position]) return s;
      return { ...s, players: [...s.players, { player_id: p.id, position: p.position, is_starting: s.players.length < 11, price_paid: p.price }] };
    });
  };

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

  return (
    <div data-testid="fantasy-hub">
      <div className="cp-surface p-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>FIFA WC 2026 · Fantasy</div>
          <h1 className="text-xl font-extrabold mt-0.5">{comp?.name || "Build Your Squad"}</h1>
          <p className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>{comp?.squad_size || 15} players · Budget £{budget}m · {comp?.transfers_per_gw || 1} transfer/GW</p>
        </div>
        <div className="flex items-center gap-2">
          {!user && <Link to="/signin" className="cp-btn-primary" data-testid="fantasy-signin-cta">Sign in to save</Link>}
          {user && <button onClick={save} disabled={overBudget || overSize || squad.players.length === 0} className="cp-btn-primary disabled:opacity-50" data-testid="fantasy-save-btn">
            {saved ? <><Check size={14}/> Saved</> : "Save Squad"}
          </button>}
        </div>
      </div>

      {(err || overBudget || overSize) && (
        <div className="cp-surface p-3 text-sm mt-3 flex items-center gap-2" style={{ borderColor: "#FF3D52", color: "#FF3D52" }}>
          <AlertTriangle size={14}/>
          {err || (overBudget ? `Over budget: £${totalCost.toFixed(1)}m / £${budget}m` : `Squad too large: ${squad.players.length} / ${comp?.squad_size || 15}`)}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-4 mt-3">
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
                <button key={p.id} onClick={() => togglePlayer(p)} disabled={!inSquad && (squad.players.length >= (comp?.squad_size || 15) || posFull)} className="w-full px-3 py-2 flex items-center gap-3 text-sm hover:bg-white/5 text-left disabled:opacity-40" data-testid={`player-${p.id}`}>
                  {p.team_logo && <img src={p.team_logo} className="w-5 h-5 object-contain" alt="" onError={(e)=>{e.target.style.display="none"}}/>}
                  <div className="flex-1 min-w-0">
                    <div className="truncate font-medium">{p.name}</div>
                    <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{p.team_name} · {p.position}</div>
                  </div>
                  <span className="cp-pill" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text)" }}>£{(p.price || 5).toFixed(1)}m</span>
                  {inSquad && <Check size={14} className="text-cp-lime"/>}
                </button>
              );
            })}
          </div>
        </section>

        <aside className="cp-surface h-fit lg:sticky lg:top-[110px]">
          <div className="cp-card-header normal-case">
            <span className="flex items-center gap-2 font-bold" style={{ color: "var(--cp-text)" }}><ShieldCheck size={14} className="text-cp-lime"/> Your Squad ({squad.players.length}/15)</span>
            <span className="text-[10px]" style={{ color: overBudget ? "#FF3D52" : "var(--cp-text-muted)" }}>£{totalCost.toFixed(1)}m / £{budget}m</span>
          </div>
          {POSITIONS.map(pos => (
            <div key={pos} className="p-2 border-b" style={{ borderColor: "var(--cp-border)" }}>
              <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--cp-text-muted)" }}>{pos} ({counts[pos] || 0}/{POS_LIMIT[pos]})</div>
              <ul className="space-y-1">
                {squad.players.filter(p => p.position === pos).map(p => {
                  const meta = players.find(x => x.id === p.player_id);
                  if (!meta) return null;
                  return (
                    <li key={p.player_id} className="flex items-center gap-2 text-sm">
                      <span className="flex-1 truncate">{meta.name}</span>
                      <button onClick={() => setSquad(s => ({ ...s, captain: s.captain === p.player_id ? null : p.player_id }))} className={`p-1 rounded ${squad.captain === p.player_id ? "text-cp-lime" : "opacity-50 hover:opacity-100"}`} title="Captain" data-testid={`captain-${p.player_id}`}>
                        <Star size={12} fill={squad.captain === p.player_id ? "#A3E635" : "transparent"}/>
                      </button>
                      <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>£{p.price_paid?.toFixed?.(1) || meta.price?.toFixed?.(1) || "5.0"}m</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </aside>
      </div>
    </div>
  );
};

export default FantasyHub;
