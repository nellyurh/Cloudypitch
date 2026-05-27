import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { Globe2 } from "lucide-react";

export const LeftSidebar = ({ sport = "football" }) => {
  const [countries, setCountries] = useState([]);
  const [leagues, setLeagues] = useState([]);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    (async () => {
      try {
        const [c, l] = await Promise.all([
          api.get(`/countries?sport=${sport}`),
          api.get(`/leagues?sport=${sport}&limit=200`),
        ]);
        setCountries(c.data.countries || []);
        setLeagues(l.data.leagues || []);
      } catch (_) {}
    })();
  }, [sport]);

  const leaguesByCountry = leagues.reduce((acc, l) => {
    const k = l.country || "World";
    acc[k] = acc[k] || [];
    acc[k].push(l);
    return acc;
  }, {});

  return (
    <aside className="cp-surface p-0 sticky top-[110px] h-fit max-h-[calc(100vh-130px)] overflow-y-auto scrollbar-thin" data-testid="left-sidebar">
      <div className="cp-card-header">
        <span className="flex items-center gap-2 normal-case font-bold tracking-wide" style={{ color: "var(--cp-text)" }}>
          <Globe2 size={14} className="text-cp-lime" />
          Countries
        </span>
        <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{countries.length}</span>
      </div>
      <ul className="text-sm">
        {countries.map((c) => {
          const ls = leaguesByCountry[c.country] || [];
          const open = expanded[c.country];
          return (
            <li key={c.country} className="border-b" style={{ borderColor: "var(--cp-border)" }}>
              <button
                onClick={() => setExpanded(s => ({ ...s, [c.country]: !s[c.country] }))}
                className="w-full px-3 py-2 flex items-center justify-between hover:bg-white/5"
                data-testid={`sidebar-country-${c.country.toLowerCase().replace(/\s+/g, "-")}`}
              >
                <span className="truncate">{c.country}</span>
                <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{c.league_count}</span>
              </button>
              {open && ls.length > 0 && (
                <ul className="pb-2">
                  {ls.map(l => (
                    <li key={l.id}>
                      <Link
                        to={`/league/${l.id}`}
                        className="block px-6 py-1.5 text-xs truncate hover:text-cp-lime"
                        style={{ color: "var(--cp-text-muted)" }}
                        data-testid={`sidebar-league-${l.id}`}
                      >
                        {l.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </aside>
  );
};

export default LeftSidebar;
