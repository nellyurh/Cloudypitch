import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../lib/api";
import { MatchRow } from "../components/MatchRow";
import { ChevronLeft } from "lucide-react";

const TABS = [
  { id: "fixtures", label: "Fixtures" },
  { id: "standings", label: "Standings" },
  { id: "scorers", label: "Top Scorers" },
];

export const LeaguePage = () => {
  const { id } = useParams();
  const [lg, setLg] = useState(null);
  const [matches, setMatches] = useState([]);
  const [standings, setStandings] = useState([]);
  const [scorers, setScorers] = useState([]);
  const [tab, setTab] = useState("fixtures");

  useEffect(() => {
    (async () => {
      try {
        const [a, b, c, d] = await Promise.all([
          api.get(`/leagues/${id}`),
          api.get(`/leagues/${id}/fixtures`),
          api.get(`/leagues/${id}/standings`),
          api.get(`/leagues/${id}/scorers`),
        ]);
        setLg(a.data.league);
        setMatches(b.data.matches || []);
        setStandings(c.data.standings || []);
        setScorers(d.data.scorers || []);
      } catch (_) {}
    })();
  }, [id]);

  if (!lg) return <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>Loading league…</div>;

  return (
    <div className="max-w-4xl mx-auto" data-testid="league-page">
      <Link to="/" className="inline-flex items-center gap-1 text-sm mb-2 hover:text-cp-lime"><ChevronLeft size={14}/> Back</Link>
      <div className="cp-surface p-4 flex items-center gap-3">
        {lg.logo_url && <img src={lg.logo_url} className="w-10 h-10 object-contain" alt="" onError={(e)=>{e.target.style.display="none"}}/>}
        <div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{lg.country}</div>
          <div className="text-lg font-extrabold">{lg.name}</div>
        </div>
      </div>

      <div className="flex gap-1 mt-3 cp-surface p-1 w-fit">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`px-3 py-1.5 text-sm rounded transition ${tab === t.id ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid={`league-tab-${t.id}`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-3">
        {tab === "fixtures" && (
          <div className="cp-surface overflow-hidden">
            {matches.length === 0 && <div className="p-4 text-sm" style={{ color: "var(--cp-text-muted)" }}>No fixtures yet.</div>}
            {matches.map(m => <MatchRow key={m.id} m={m} />)}
          </div>
        )}
        {tab === "standings" && (
          standings.length === 0 ? <div className="cp-surface p-4 text-sm" style={{ color: "var(--cp-text-muted)" }}>Standings not yet ingested for this league.</div> :
          <table className="w-full text-sm cp-surface">
            <thead><tr style={{ color: "var(--cp-text-muted)" }} className="text-xs">
              <th className="text-left p-2">#</th><th className="text-left">Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>Pts</th>
            </tr></thead>
            <tbody>{standings.map((s, i) => (
              <tr key={i} className="border-t" style={{ borderColor: "var(--cp-border)" }}>
                <td className="p-2">{s.rank}</td><td>{s.team_name || s.team_id}</td><td className="text-center">{s.MP}</td><td className="text-center">{s.W}</td><td className="text-center">{s.D}</td><td className="text-center">{s.L}</td><td className="text-center">{s.GF}</td><td className="text-center">{s.GA}</td><td className="text-center font-bold text-cp-lime">{s.points}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
        {tab === "scorers" && (
          scorers.length === 0 ? <div className="cp-surface p-4 text-sm" style={{ color: "var(--cp-text-muted)" }}>Top scorers not yet ingested for this league.</div> :
          <ul className="cp-surface divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {scorers.map((s, i) => (
              <li key={i} className="px-3 py-2 flex items-center gap-3 text-sm">
                <span className="cp-logo-circle text-[10px]" style={{ width: 20, height: 20 }}>{s.rank}</span>
                <span className="flex-1">{s.player_name}</span>
                <span className="tabular-nums font-bold text-cp-lime">{s.goals}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default LeaguePage;
