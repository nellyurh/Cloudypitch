import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ChevronLeft, Trophy, Users2, Calendar } from "lucide-react";
import api from "../lib/api";
import { flagUrl } from "../lib/flags";

/** Team detail page — Sofascore-style.
 *   Header: flag + team name + group badge
 *   Tabs: Standings / Players / Schedule / Details
 *   Pulls everything from /api/teams/{team_id} which reads from Sportmonks-backed Mongo.
 */
export default function TeamView() {
  const { teamId } = useParams();
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("standings");
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data: d } = await api.get(`/teams/${teamId}`);
        if (!cancelled) setData(d);
      } catch (_e) { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, [teamId]);

  if (!data) return <div className="cp-surface p-8 text-center text-sm" data-testid="team-loading">Loading team data…</div>;
  const t = data.team || {};
  const flag = flagUrl(t.name, 80);

  return (
    <div className="space-y-3" data-testid="team-view">
      <Link to="/worldcup" className="inline-flex items-center gap-1 text-xs hover:text-cp-lime" data-testid="team-back">
        <ChevronLeft size={14}/> Back to World Cup
      </Link>

      {/* Hero */}
      <div className="cp-surface overflow-hidden">
        <div className="p-4 md:p-6 flex items-start gap-4" style={{ background: "linear-gradient(135deg, rgba(15,110,86,0.2), transparent 60%)" }}>
          {flag && <img src={flag} alt="" className="w-16 h-12 md:w-20 md:h-14 object-cover rounded ring-2 ring-black/30" data-testid="team-flag"/>}
          <div className="flex-1 min-w-0">
            <h1 className="text-xl md:text-2xl font-extrabold leading-tight" data-testid="team-name">{t.name}</h1>
            <div className="text-xs mt-1 flex items-center gap-3" style={{ color: "var(--cp-text-muted)" }}>
              {data.group && (
                <span className="inline-flex items-center gap-1">
                  <Trophy size={12} className="text-cp-lime"/> Group {data.group}
                </span>
              )}
              <span className="inline-flex items-center gap-1">
                <Users2 size={12}/> Squad: {(data.squad || []).length} players
              </span>
              {t.country && <span>Country: {t.country}</span>}
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 px-2 py-1.5 border-t overflow-x-auto" style={{ borderColor: "var(--cp-border)" }}>
          {[
            { k: "standings", label: "Standings" },
            { k: "players", label: "Players" },
            { k: "schedule", label: "Schedule" },
            { k: "details", label: "Details" },
          ].map(x => (
            <button key={x.k} onClick={() => setTab(x.k)} className="text-xs font-extrabold px-3 py-2 transition"
              style={{ color: tab === x.k ? "var(--cp-text)" : "var(--cp-text-muted)", borderBottom: tab === x.k ? "2px solid var(--cp-lime)" : "2px solid transparent" }}
              data-testid={`team-tab-${x.k}`}>
              {x.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab panes */}
      {tab === "standings" && <StandingsPane group={data.group} table={data.group_table || []} thisTeam={t.name}/>}
      {tab === "players" && <PlayersPane squad={data.squad || []}/>}
      {tab === "schedule" && <SchedulePane upcoming={data.upcoming_matches || []} recent={data.recent_matches || []}/>}
      {tab === "details" && <DetailsPane team={t}/>}
    </div>
  );
}

function StandingsPane({ group, table, thisTeam }) {
  return (
    <div className="cp-surface overflow-hidden">
      <div className="px-3 py-2 text-xs font-extrabold border-b" style={{ borderColor: "var(--cp-border)" }}>
        {group ? `Group ${group} standings` : "Standings"}
      </div>
      {!group && <div className="p-4 text-xs" style={{ color: "var(--cp-text-muted)" }}>This team isn&apos;t currently mapped to a 2026 group.</div>}
      <div className="mb-2 mx-3 mt-2 rounded p-2 text-[11px] font-bold flex items-center gap-2" style={{ background: "rgba(163,230,53,0.08)", border: "1px solid rgba(163,230,53,0.2)", color: "var(--cp-text-muted)" }}>
        <Trophy size={12} className="text-cp-lime"/> Standings unlock when the first match kicks off on <b>11 June 2026</b>.
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr style={{ color: "var(--cp-text-muted)" }} className="text-[10px] uppercase tracking-widest">
            <th className="text-left font-normal px-3 py-1.5">#</th>
            <th className="text-left font-normal py-1.5">Team</th>
            <th className="font-normal py-1.5">P</th>
            <th className="font-normal py-1.5">W</th>
            <th className="font-normal py-1.5">D</th>
            <th className="font-normal py-1.5">L</th>
            <th className="font-normal py-1.5 pr-3">PTS</th>
          </tr>
        </thead>
        <tbody>
          {table.map((r, i) => (
            <tr key={r.team} className="border-t" style={{ borderColor: "var(--cp-border)", background: r.team === thisTeam ? "rgba(163,230,53,0.08)" : "transparent" }} data-testid={`team-standings-row-${r.team}`}>
              <td className="px-3 py-1.5 font-bold">{i + 1}</td>
              <td className="py-1.5 flex items-center gap-1.5">
                {flagUrl(r.team, 40) && <img src={flagUrl(r.team, 40)} className="w-4 h-3 rounded-sm object-cover ring-1 ring-black/30" alt=""/>}
                <span>{r.team}</span>
              </td>
              <td className="text-center tabular-nums">{r.P}</td>
              <td className="text-center tabular-nums">{r.W}</td>
              <td className="text-center tabular-nums">{r.D}</td>
              <td className="text-center tabular-nums">{r.L}</td>
              <td className="text-center font-extrabold text-cp-lime tabular-nums pr-3">{r.PTS}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PlayersPane({ squad }) {
  if (squad.length === 0) {
    return <div className="cp-surface p-4 text-xs text-center" style={{ color: "var(--cp-text-muted)" }} data-testid="team-no-players">Squad data unlocks once teams announce their final 26-man rosters (typically end of May 2026).</div>;
  }
  const grouped = squad.reduce((acc, p) => { const k = p.position || "OTH"; (acc[k] = acc[k] || []).push(p); return acc; }, {});
  return (
    <div className="space-y-3" data-testid="team-players-pane">
      {["GK", "DEF", "MID", "FWD", "OTH"].filter(k => grouped[k]).map(k => (
        <div key={k} className="cp-surface overflow-hidden">
          <div className="px-3 py-1.5 text-[10px] uppercase tracking-widest font-bold" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>{k}</div>
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {grouped[k].map(p => (
              <li key={p.id} className="px-3 py-2 flex items-center gap-3 text-xs" data-testid={`team-player-${p.id}`}>
                <span className="w-7 h-7 rounded-full text-[10px] font-extrabold flex items-center justify-center" style={{ background: "var(--cp-surface-2)" }}>{p.shirt_number || "—"}</span>
                <span className="flex-1 font-bold truncate">{p.name}</span>
                <span className="tabular-nums text-cp-lime">£{p.price?.toFixed(1) || "—"}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function SchedulePane({ upcoming, recent }) {
  return (
    <div className="space-y-3" data-testid="team-schedule-pane">
      {upcoming.length > 0 && (
        <div className="cp-surface overflow-hidden">
          <div className="px-3 py-1.5 text-[10px] uppercase tracking-widest font-bold" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>Upcoming</div>
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {upcoming.map(m => <MatchRow key={m.id} m={m}/>)}
          </ul>
        </div>
      )}
      {recent.length > 0 && (
        <div className="cp-surface overflow-hidden">
          <div className="px-3 py-1.5 text-[10px] uppercase tracking-widest font-bold" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>Recent</div>
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {recent.map(m => <MatchRow key={m.id} m={m} showScore/>)}
          </ul>
        </div>
      )}
      {!upcoming.length && !recent.length && (
        <div className="cp-surface p-4 text-xs text-center" style={{ color: "var(--cp-text-muted)" }}>No matches found for this team yet.</div>
      )}
    </div>
  );
}

function MatchRow({ m, showScore }) {
  return (
    <li className="px-3 py-2 grid grid-cols-[80px_1fr_auto] gap-3 items-center text-xs">
      <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
        <Calendar size={10} className="inline mr-1"/>{(m.scheduled_at || "").slice(0, 10)}
      </span>
      <span className="truncate font-bold">{m.home_team_name} <span className="opacity-50">v</span> {m.away_team_name}</span>
      {showScore && <span className="tabular-nums font-extrabold text-cp-lime">{m.home_score}–{m.away_score}</span>}
    </li>
  );
}

function DetailsPane({ team }) {
  const fields = [
    ["Name", team.name],
    ["Short name", team.short_name],
    ["Country", team.country],
    ["Founded", team.founded],
    ["Stadium", team.venue],
    ["Coach", team.coach],
    ["Sportmonks ID", team.sportmonks_id],
  ].filter(([, v]) => v);
  return (
    <div className="cp-surface p-4" data-testid="team-details-pane">
      <dl className="grid grid-cols-2 gap-y-2 text-xs">
        {fields.map(([k, v]) => (
          <React.Fragment key={k}>
            <dt className="opacity-60">{k}</dt>
            <dd className="font-bold">{v}</dd>
          </React.Fragment>
        ))}
      </dl>
      {fields.length === 0 && <div className="text-xs" style={{ color: "var(--cp-text-muted)" }}>Details pending — Sportmonks team enrichment runs on the next ingestion cycle.</div>}
    </div>
  );
}
