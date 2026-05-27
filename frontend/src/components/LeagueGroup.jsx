import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, Star } from "lucide-react";
import { MatchRow } from "./MatchRow";
import api from "../lib/api";
import { useAuth } from "../lib/auth";

const LS_KEY = "cp:favorites";
function lsGet() { try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch { return []; } }
function lsSet(items) { try { localStorage.setItem(LS_KEY, JSON.stringify(items)); } catch { /* ignore */ } }

export const LeagueGroup = ({ group, sport = "football" }) => {
  const { user } = useAuth();
  const [open, setOpen] = useState(true);
  const [pinned, setPinned] = useState(false);

  const checkPinned = useCallback(async () => {
    if (user) {
      try {
        const { data } = await api.get("/users/me/favorites");
        const has = (data.favorites || []).some(f => f.entity_type === "league" && f.entity_id === group.league_id);
        setPinned(has);
      } catch { /* ignore */ }
    } else {
      setPinned(lsGet().some(f => f.entity_type === "league" && f.entity_id === group.league_id));
    }
  }, [user, group.league_id]);

  useEffect(() => { checkPinned(); }, [checkPinned]);
  useEffect(() => {
    const h = () => checkPinned();
    window.addEventListener("cp:favorites:changed", h);
    return () => window.removeEventListener("cp:favorites:changed", h);
  }, [checkPinned]);

  const togglePin = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (user) {
      try {
        if (pinned) await api.delete(`/users/me/favorites/league/${group.league_id}`);
        else await api.post(`/users/me/favorites/league/${group.league_id}`);
      } catch { /* ignore */ }
    } else {
      const cur = lsGet();
      if (pinned) {
        lsSet(cur.filter(f => !(f.entity_type === "league" && f.entity_id === group.league_id)));
      } else {
        lsSet([...cur, { entity_type: "league", entity_id: group.league_id, name: group.league_name, country: group.league_country, logo_url: group.league_logo }]);
      }
    }
    setPinned(p => !p);
    window.dispatchEvent(new Event("cp:favorites:changed"));
  };

  if (!group?.matches?.length) return null;
  return (
    <div className="cp-surface mb-3 overflow-hidden animate-fade-in" data-testid={`league-group-${group.league_id}`}>
      <div className="cp-card-header">
        <button onClick={() => setOpen(o => !o)} className="flex items-center gap-2 normal-case flex-1 text-left" data-testid={`league-toggle-${group.league_id}`}>
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {group.league_logo ? (
            <img src={group.league_logo} alt="" className="w-4 h-4 object-contain" onError={(e) => { e.target.style.display = "none"; }} />
          ) : null}
          <span className="text-xs" style={{ color: "var(--cp-text-muted)" }}>{group.league_country}</span>
          <span className="text-xs font-bold tracking-wide" style={{ color: "var(--cp-text)" }}>{group.league_name}</span>
        </button>
        <div className="flex items-center gap-2">
          <button onClick={togglePin} className="hover:scale-110 transition" aria-label="Pin league" data-testid={`pin-league-${group.league_id}`}>
            <Star size={13} className={pinned ? "text-cp-lime" : ""} fill={pinned ? "#A3E635" : "transparent"} style={!pinned ? { color: "var(--cp-text-muted)" } : {}} />
          </button>
          <Link
            to={`/league/${group.league_id}`}
            onClick={(e) => e.stopPropagation()}
            className="text-[10px] uppercase tracking-wider hover:text-cp-lime"
            data-testid={`league-link-${group.league_id}`}
          >View →</Link>
        </div>
      </div>
      {open && (
        <div>
          {group.matches.map((m) => <MatchRow key={m.id} m={m} sport={sport} />)}
        </div>
      )}
    </div>
  );
};

export default LeagueGroup;
