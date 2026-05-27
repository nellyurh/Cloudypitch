import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { Link } from "react-router-dom";
import { Trophy, Coins } from "lucide-react";
import { MatchRow } from "../components/MatchRow";

function CountdownLarge({ to }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const ms = new Date(to).getTime() - now;
  const d = Math.max(0, Math.floor(ms / 86400000));
  const h = Math.max(0, Math.floor((ms % 86400000) / 3600000));
  const min = Math.max(0, Math.floor((ms % 3600000) / 60000));
  const s = Math.max(0, Math.floor((ms % 60000) / 1000));
  const B = ({ v, l }) => (
    <div className="text-center px-3 md:px-5 py-2 cp-surface min-w-[80px]">
      <div className="text-3xl md:text-5xl font-extrabold tabular-nums" style={{ color: "#A3E635" }}>{String(v).padStart(2, "0")}</div>
      <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{l}</div>
    </div>
  );
  return <div className="flex items-center justify-center gap-2 md:gap-3 flex-wrap" data-testid="wc-hub-countdown"><B v={d} l="Days"/><B v={h} l="Hours"/><B v={min} l="Mins"/><B v={s} l="Secs"/></div>;
}

export const WorldCupHub = () => {
  const [data, setData] = useState(null);
  useEffect(() => { (async () => { try { const { data } = await api.get("/worldcup"); setData(data); } catch (_) {} })(); }, []);
  return (
    <div data-testid="worldcup-hub">
      <div
        className="relative overflow-hidden rounded-xl"
        style={{
          background: `linear-gradient(180deg, rgba(6,78,59,0.7) 0%, rgba(26,31,38,0.92) 90%), url('https://images.unsplash.com/photo-1705593973313-75de7bf95b56?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NjZ8MHwxfHNlYXJjaHwxfHxmb290YmFsbCUyMHN0YWRpdW0lMjBjcm93ZHxlbnwwfHx8fDE3Nzk5MTk4MTF8MA&ixlib=rb-4.1.0&q=85')`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="px-6 md:px-10 py-10 md:py-14 text-white">
          <div className="inline-flex items-center gap-2 cp-pill" style={{ background: "rgba(163,230,53,0.2)", color: "#A3E635" }}>
            <Trophy size={12}/> FIFA WORLD CUP 2026
          </div>
          <h1 className="text-3xl md:text-5xl font-extrabold mt-3 tracking-tight">USA · Canada · Mexico</h1>
          <p className="text-sm md:text-base mt-1" style={{ color: "rgba(255,255,255,0.85)" }}>48 teams · 12 groups · One champion · Predict, build squads, win the pool.</p>
          <div className="mt-5"><CountdownLarge to="2026-06-11T18:00:00+00:00" /></div>
          <div className="flex gap-2 mt-5">
            <Link to="/predictions" className="cp-btn-primary" data-testid="wc-cta-predict">Make Predictions</Link>
            <Link to="/fantasy" className="cp-btn-ghost text-white" data-testid="wc-cta-fantasy" style={{ background: "rgba(255,255,255,0.08)", borderColor: "rgba(255,255,255,0.2)" }}>Build Fantasy Squad</Link>
          </div>
        </div>
      </div>

      <h2 className="text-xl font-extrabold mt-6 mb-3">Group Stage</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {(data?.groups || []).map(g => (
          <div key={g.group} className="cp-surface p-3" data-testid={`group-${g.group}`}>
            <div className="text-[11px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Group {g.group}</div>
            <ul className="mt-2 space-y-1.5">
              {(g.teams || []).map(t => (
                <li key={t} className="text-sm flex items-center justify-between">
                  <span>{t}</span>
                  <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>—</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {data?.prize_pool && (
        <div className="cp-surface mt-6 p-4 flex flex-col md:flex-row md:items-center gap-3" data-testid="wc-prize-pool-card">
          <Coins size={28} className="text-cp-lime" />
          <div className="flex-1">
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Grand Prize Pool</div>
            <div className="text-lg font-bold">{data.prize_pool.title}</div>
            <div className="text-2xl font-extrabold text-cp-lime">₦{(data.prize_pool.amount_total_ngn || 0).toLocaleString()}</div>
          </div>
          <Link to={`/prize-pool/${data.prize_pool.id}`} className="cp-btn-primary" data-testid="wc-prize-cta">View Payouts</Link>
        </div>
      )}

      {(data?.matches?.length || 0) > 0 && (
        <>
          <h2 className="text-xl font-extrabold mt-6 mb-3">WC Fixtures</h2>
          <div className="cp-surface overflow-hidden">
            {data.matches.map(m => <MatchRow key={m.id} m={m} />)}
          </div>
        </>
      )}
    </div>
  );
};

export default WorldCupHub;
