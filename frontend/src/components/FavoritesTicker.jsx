import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Star, X, Search as SearchIcon, Plus } from "lucide-react";
import api from "../lib/api";
import { useAuth } from "../lib/auth";

/**
 * FavoritesTicker — shows user's pinned leagues/teams on the right rail.
 * - Logged-in users: fetches /api/users/me/favorites + their entity metadata.
 * - Anonymous users: persists favorites in localStorage so the feature is usable
 *   even before signup (UX-positive).
 */
const LS_KEY = "cp:favorites";

function lsGet() {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch { return []; }
}
function lsSet(items) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(items)); } catch { /* ignore */ }
}

export const FavoritesTicker = () => {
  const { user } = useAuth();
  const [items, setItems] = useState([]);  // [{entity_type, entity_id, name, country, logo_url}]
  const [adding, setAdding] = useState(false);
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);

  const load = useCallback(async () => {
    if (user) {
      try {
        const { data } = await api.get("/users/me/favorites");
        const favs = data.favorites || [];
        // Hydrate league metadata
        const leagueIds = favs.filter(f => f.entity_type === "league").map(f => f.entity_id);
        const teamIds = favs.filter(f => f.entity_type === "team").map(f => f.entity_id);
        const hydrated = [];
        if (leagueIds.length > 0) {
          const lookups = await Promise.all(leagueIds.map(id => api.get(`/leagues/${id}`).catch(() => null)));
          lookups.forEach((res, i) => {
            const lg = res?.data?.league;
            if (lg) hydrated.push({ entity_type: "league", entity_id: leagueIds[i], name: lg.name, country: lg.country, logo_url: lg.logo_url });
          });
        }
        // Teams: we don't have a dedicated /teams/:id, but data may include name in localStorage cache
        teamIds.forEach(id => hydrated.push({ entity_type: "team", entity_id: id, name: id, country: "" }));
        setItems(hydrated);
      } catch (_) { setItems([]); }
    } else {
      setItems(lsGet());
    }
  }, [user]);

  useEffect(() => { load(); }, [load]);

  // Listen to a global "favorites changed" event so other components can refresh us
  useEffect(() => {
    const h = () => load();
    window.addEventListener("cp:favorites:changed", h);
    return () => window.removeEventListener("cp:favorites:changed", h);
  }, [load]);

  const remove = async (it) => {
    if (user) {
      try { await api.delete(`/users/me/favorites/${it.entity_type}/${it.entity_id}`); } catch (_) {}
    } else {
      lsSet(items.filter(x => !(x.entity_type === it.entity_type && x.entity_id === it.entity_id)));
    }
    load();
    window.dispatchEvent(new Event("cp:favorites:changed"));
  };

  const add = async (lg) => {
    const payload = { entity_type: "league", entity_id: lg.id, name: lg.name, country: lg.country, logo_url: lg.logo_url };
    if (user) {
      try { await api.post(`/users/me/favorites/league/${lg.id}`); } catch (_) {}
    } else {
      const existing = lsGet();
      if (!existing.find(x => x.entity_type === "league" && x.entity_id === lg.id)) {
        lsSet([...existing, payload]);
      }
    }
    setQ(""); setResults([]); setAdding(false);
    load();
    window.dispatchEvent(new Event("cp:favorites:changed"));
  };

  const search = async (val) => {
    setQ(val);
    if (val.length < 2) { setResults([]); return; }
    try {
      const { data } = await api.get(`/search?q=${encodeURIComponent(val)}`);
      setResults((data.leagues || []).slice(0, 8));
    } catch (_) { setResults([]); }
  };

  return (
    <div className="cp-surface overflow-hidden" data-testid="favorites-ticker">
      <div className="cp-card-header normal-case">
        <span className="flex items-center gap-2 font-bold tracking-wide" style={{ color: "var(--cp-text)" }}>
          <Star size={14} className="text-cp-lime" fill="#A3E635" />
          Pinned
        </span>
        <button onClick={() => setAdding(a => !a)} className="text-[10px] uppercase tracking-wider hover:text-cp-lime flex items-center gap-1" data-testid="favorites-add-toggle">
          {adding ? <X size={11}/> : <><Plus size={11}/> Add</>}
        </button>
      </div>

      {adding && (
        <div className="p-2 border-b" style={{ borderColor: "var(--cp-border)" }}>
          <div className="relative">
            <SearchIcon size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-cp-muted"/>
            <input
              value={q}
              onChange={(e) => search(e.target.value)}
              placeholder="Find a league…"
              className="cp-input pl-7 text-xs !py-1.5"
              autoFocus
              data-testid="favorites-search-input"
            />
          </div>
          {results.length > 0 && (
            <ul className="mt-2 space-y-1 max-h-48 overflow-y-auto scrollbar-thin">
              {results.map(lg => (
                <li key={lg.id}>
                  <button onClick={() => add(lg)} className="w-full flex items-center gap-2 px-2 py-1.5 text-xs hover:bg-white/5 rounded text-left" data-testid={`fav-add-${lg.id}`}>
                    {lg.logo_url ? <img src={lg.logo_url} className="w-3.5 h-3.5 object-contain" alt="" onError={(e)=>{e.target.style.display="none"}}/> : <span className="w-3.5 h-3.5"/>}
                    <span className="flex-1 truncate">{lg.name}</span>
                    <span className="text-[9px]" style={{ color: "var(--cp-text-muted)" }}>{lg.country}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {items.length === 0 ? (
        <div className="px-3 py-3 text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
          Tap <Plus size={10} className="inline"/> to pin leagues you care about. They&apos;ll always show up here.
        </div>
      ) : (
        <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
          {items.map(it => (
            <li key={`${it.entity_type}-${it.entity_id}`} className="px-3 py-2 flex items-center gap-2 text-sm group" data-testid={`fav-item-${it.entity_id}`}>
              {it.logo_url ? (
                <img src={it.logo_url} className="w-4 h-4 object-contain" alt="" onError={(e)=>{e.target.style.display="none"}}/>
              ) : (
                <Star size={12} className="text-cp-lime" fill="#A3E635" />
              )}
              <Link to={`/league/${it.entity_id}`} className="flex-1 min-w-0 truncate hover:text-cp-lime">
                {it.name}
              </Link>
              {it.country && <span className="text-[9px]" style={{ color: "var(--cp-text-muted)" }}>{it.country}</span>}
              <button onClick={() => remove(it)} className="opacity-0 group-hover:opacity-100 transition" aria-label="Remove" data-testid={`fav-remove-${it.entity_id}`}>
                <X size={12} style={{ color: "var(--cp-text-muted)" }}/>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default FavoritesTicker;
