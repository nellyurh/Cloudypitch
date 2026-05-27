import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Trophy, Flame, ChevronRight, Coins } from "lucide-react";
import api from "../lib/api";
import { FavoritesTicker } from "./FavoritesTicker";

function Countdown({ to }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const ms = new Date(to).getTime() - now;
  const d = Math.max(0, Math.floor(ms / 86400000));
  const h = Math.max(0, Math.floor((ms % 86400000) / 3600000));
  const min = Math.max(0, Math.floor((ms % 3600000) / 60000));
  const s = Math.max(0, Math.floor((ms % 60000) / 1000));
  const Box = ({ v, label }) => (
    <div className="text-center px-2">
      <div className="text-2xl md:text-3xl font-extrabold tabular-nums" style={{ color: "#A3E635" }}>{String(v).padStart(2, "0")}</div>
      <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--cp-text-muted)" }}>{label}</div>
    </div>
  );
  return (
    <div className="flex items-center justify-between mt-2" data-testid="wc-countdown">
      <Box v={d} label="Days" />
      <Box v={h} label="Hrs" />
      <Box v={min} label="Min" />
      <Box v={s} label="Sec" />
    </div>
  );
}

export const RightRail = () => {
  const [board, setBoard] = useState([]);
  const [pool, setPool] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [lb, pools] = await Promise.all([
          api.get("/predictions/leaderboard?limit=5"),
          api.get("/prize-pools"),
        ]);
        setBoard(lb.data.leaderboard || []);
        setPool((pools.data.pools || []).find(p => p.kind === "fantasy_wc2026") || (pools.data.pools || [])[0] || null);
      } catch (_) {}
    })();
  }, []);

  return (
    <aside className="space-y-3" data-testid="right-rail">
      {/* Pinned / Favorites ticker */}
      <FavoritesTicker />

      {/* WC 2026 Banner */}
      <div className="cp-surface overflow-hidden">
        <div
          className="relative h-32 flex items-end p-3"
          style={{
            background: `linear-gradient(180deg, rgba(6,78,59,0) 0%, rgba(26,31,38,0.92) 95%), url('https://images.unsplash.com/photo-1705593973313-75de7bf95b56?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NjZ8MHwxfHNlYXJjaHwxfHxmb290YmFsbCUyMHN0YWRpdW0lMjBjcm93ZHxlbnwwfHx8fDE3Nzk5MTk4MTF8MA&ixlib=rb-4.1.0&q=85')`,
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        >
          <div>
            <div className="text-[10px] uppercase tracking-widest text-cp-lime font-bold">FIFA World Cup 2026</div>
            <div className="text-white text-base font-extrabold leading-tight">Kicks off June 11, 2026</div>
          </div>
        </div>
        <div className="p-3">
          <Countdown to="2026-06-11T18:00:00+00:00" />
          <Link to="/worldcup" className="cp-btn-primary w-full mt-3 justify-center" data-testid="wc-cta">
            <Trophy size={14} /> Explore WC Hub
          </Link>
        </div>
      </div>

      {/* Predictions leaderboard preview */}
      <div className="cp-surface overflow-hidden">
        <div className="cp-card-header normal-case">
          <span className="flex items-center gap-2 font-bold tracking-wide" style={{ color: "var(--cp-text)" }}>
            <Flame size={14} className="text-cp-lime" />
            Predictions Top 5
          </span>
          <Link to="/leaderboards" className="text-[10px] uppercase tracking-wider hover:text-cp-lime">All →</Link>
        </div>
        <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
          {board.length === 0 && (
            <li className="px-3 py-3 text-xs" style={{ color: "var(--cp-text-muted)" }}>Be the first to predict!</li>
          )}
          {board.map((r) => (
            <li key={r.user_id} className="px-3 py-2 flex items-center gap-2 text-sm">
              <span className="cp-logo-circle text-[10px]" style={{ width: 22, height: 22 }}>{r.rank}</span>
              <span className="truncate flex-1">{r.display_name}</span>
              <span className="tabular-nums font-bold text-cp-lime">{r.total_points}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Prize pool */}
      {pool && (
        <Link to={`/prize-pool/${pool.id}`} className="block cp-surface p-3 hover:bg-white/5 transition" data-testid="featured-prize-pool">
          <div className="flex items-start gap-2">
            <Coins size={20} className="text-cp-lime mt-0.5" />
            <div className="flex-1">
              <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Featured Prize Pool</div>
              <div className="text-sm font-bold leading-tight mt-0.5">{pool.title}</div>
              <div className="text-xl font-extrabold mt-1 text-cp-lime">₦{(pool.amount_total_ngn || 0).toLocaleString()}</div>
            </div>
            <ChevronRight size={16} className="mt-1" />
          </div>
        </Link>
      )}
    </aside>
  );
};

export default RightRail;
