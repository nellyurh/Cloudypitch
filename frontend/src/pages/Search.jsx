import React, { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import api from "../lib/api";
import { MatchRow } from "../components/MatchRow";

export const SearchPage = () => {
  const [params] = useSearchParams();
  const q = params.get("q") || "";
  const [res, setRes] = useState({ teams: [], leagues: [], matches: [] });
  useEffect(() => { if (q.length >= 2) (async () => { try { const { data } = await api.get(`/search?q=${encodeURIComponent(q)}`); setRes(data); } catch (_) {} })(); }, [q]);
  return (
    <div data-testid="search-page">
      <h1 className="text-xl font-extrabold mb-3">Search: <span className="text-cp-lime">"{q}"</span></h1>
      {(res.leagues.length + res.teams.length + res.matches.length) === 0 && <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>No results yet. Data may still be ingesting.</div>}
      {res.leagues.length > 0 && <section className="mb-4">
        <div className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--cp-text-muted)" }}>Leagues</div>
        <div className="cp-surface divide-y" style={{ borderColor: "var(--cp-border)" }}>
          {res.leagues.map(l => <Link key={l.id} to={`/league/${l.id}`} className="block px-3 py-2 text-sm hover:bg-white/5">{l.name} <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>· {l.country}</span></Link>)}
        </div>
      </section>}
      {res.teams.length > 0 && <section className="mb-4">
        <div className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--cp-text-muted)" }}>Teams</div>
        <div className="cp-surface divide-y" style={{ borderColor: "var(--cp-border)" }}>
          {res.teams.map(t => <div key={t.id} className="px-3 py-2 text-sm">{t.name} <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>· {t.country}</span></div>)}
        </div>
      </section>}
      {res.matches.length > 0 && <section>
        <div className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--cp-text-muted)" }}>Matches</div>
        <div className="cp-surface overflow-hidden">{res.matches.map(m => <MatchRow key={m.id} m={m}/>)}</div>
      </section>}
    </div>
  );
};

export default SearchPage;
