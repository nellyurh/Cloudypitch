import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../lib/api";
import { Coins, Trophy, ChevronLeft } from "lucide-react";

const fmtUsd = (cents) => `$${((cents || 0) / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const PrizePoolsList = () => {
  const [pools, setPools] = useState([]);
  useEffect(() => {
    (async () => {
      try { const { data } = await api.get("/prize-pools"); setPools(data.pools || []); } catch (_) {}
    })();
  }, []);
  return (
    <div data-testid="prize-pools-list">
      <h1 className="text-2xl font-extrabold mb-3">Prize Pools</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {pools.map(p => (
          <Link key={p.id} to={`/prize-pool/${p.id}`} className="cp-surface p-4 hover:bg-white/5 flex items-center gap-3" data-testid={`pool-${p.id}`}>
            <Coins size={32} className="text-cp-lime"/>
            <div className="flex-1">
              <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{(p.kind || "").replace("_", " ")} · {p.status}</div>
              <div className="font-bold">{p.title}</div>
              <div className="text-xl font-extrabold text-cp-lime">{fmtUsd(p.amount_usd_cents)}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
};

export const PrizePoolDetail = () => {
  const { id } = useParams();
  const [pool, setPool] = useState(null);
  const [winners, setWinners] = useState([]);
  useEffect(() => {
    (async () => {
      try { const { data } = await api.get(`/prize-pools/${id}`); setPool(data.pool); setWinners(data.winners || []); } catch (_) {}
    })();
  }, [id]);
  if (!pool) return <div className="cp-surface p-6 text-sm" style={{ color: "var(--cp-text-muted)" }}>Loading…</div>;
  const totalCents = pool.amount_usd_cents || 0;
  const structure = pool.payout_structure;
  // Accept either list or legacy dict
  const tiers = Array.isArray(structure)
    ? structure.map(t => ({ label: `Rank ${t.rank_min}${t.rank_max > t.rank_min ? `–${t.rank_max}` : ""}`, pct: t.pct, span: t.rank_max - t.rank_min + 1 }))
    : Object.entries(structure || {}).map(([k, v]) => ({ label: `Rank ${k}`, pct: Number(v) > 1 ? Number(v) : Number(v) * 100, span: 1 }));
  return (
    <div className="max-w-3xl mx-auto" data-testid="prize-pool-detail">
      <Link to="/prize-pools" className="inline-flex items-center gap-1 text-sm mb-2 hover:text-cp-lime"><ChevronLeft size={14}/> All pools</Link>
      <div className="cp-surface p-5">
        <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>{(pool.kind || "").replace("_", " ")}</div>
        <h1 className="text-2xl font-extrabold mt-1">{pool.title}</h1>
        <div className="text-3xl font-extrabold text-cp-lime mt-2">{fmtUsd(totalCents)}</div>
        <div className="text-xs mt-1" style={{ color: "var(--cp-text-muted)" }}>
          {pool.starts_at && new Date(pool.starts_at).toLocaleDateString()} → {pool.ends_at && new Date(pool.ends_at).toLocaleDateString()}
        </div>
      </div>

      <div className="cp-surface mt-3">
        <div className="cp-card-header normal-case">
          <span className="flex items-center gap-2 font-bold" style={{ color: "var(--cp-text)" }}>
            <Trophy size={14} className="text-cp-lime"/> Payout Structure
          </span>
        </div>
        <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
          {tiers.map((t, i) => (
            <li key={i} className="px-3 py-2 flex items-center justify-between text-sm">
              <span>{t.label}</span>
              <span className="font-bold tabular-nums">
                {fmtUsd((totalCents * t.pct / 100) / Math.max(1, t.span))}
                <span className="text-[10px] ml-1" style={{ color: "var(--cp-text-muted)" }}>({t.pct}% / winner)</span>
              </span>
            </li>
          ))}
        </ul>
      </div>

      {winners.length > 0 && (
        <div className="cp-surface mt-3">
          <div className="cp-card-header normal-case font-bold">Winners</div>
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {winners.map(w => (
              <li key={w.id} className="px-3 py-2 flex items-center gap-2 text-sm">
                <span className="cp-logo-circle text-[10px]" style={{ width: 22, height: 22 }}>{w.rank}</span>
                <span className="flex-1">{w.display_name || w.user_id}</span>
                <span className="text-cp-lime font-bold tabular-nums">{fmtUsd(w.amount_usd_cents || w.amount_ngn)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default PrizePoolsList;
