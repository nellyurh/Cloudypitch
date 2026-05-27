import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight } from "lucide-react";
import { MatchRow } from "./MatchRow";

export const LeagueGroup = ({ group, sport = "football" }) => {
  const [open, setOpen] = useState(true);
  if (!group?.matches?.length) return null;
  return (
    <div className="cp-surface mb-3 overflow-hidden animate-fade-in" data-testid={`league-group-${group.league_id}`}>
      <button
        className="w-full cp-card-header"
        onClick={() => setOpen(o => !o)}
        data-testid={`league-toggle-${group.league_id}`}
      >
        <div className="flex items-center gap-2 normal-case">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {group.league_logo ? (
            <img src={group.league_logo} alt="" className="w-4 h-4 object-contain" onError={(e) => { e.target.style.display = "none"; }} />
          ) : null}
          <span className="text-xs" style={{ color: "var(--cp-text-muted)" }}>{group.league_country}</span>
          <span className="text-xs font-bold tracking-wide" style={{ color: "var(--cp-text)" }}>{group.league_name}</span>
        </div>
        <Link
          to={`/league/${group.league_id}`}
          onClick={(e) => e.stopPropagation()}
          className="text-[10px] uppercase tracking-wider hover:text-cp-lime"
          data-testid={`league-link-${group.league_id}`}
        >View →</Link>
      </button>
      {open && (
        <div>
          {group.matches.map((m) => <MatchRow key={m.id} m={m} sport={sport} />)}
        </div>
      )}
    </div>
  );
};

export default LeagueGroup;
