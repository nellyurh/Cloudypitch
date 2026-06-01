import React, { useEffect, useRef, useState } from "react";
import api from "../lib/api";
import { Zap, TrendingUp } from "lucide-react";

const USD = (cents) => `$${((cents || 0) / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/** Animated number that counts up to `target` over ~600ms. */
function CountUp({ target, prefix = "", suffix = "", decimals = 2 }) {
  const [val, setVal] = useState(target);
  const prev = useRef(target);
  useEffect(() => {
    const start = prev.current;
    const end = target;
    if (start === end) return;
    const t0 = performance.now();
    const dur = 700;
    let raf;
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(start + (end - start) * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    prev.current = end;
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return <span>{prefix}{val.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}{suffix}</span>;
}

const TIME_AGO = (iso) => {
  if (!iso) return "just now";
  try {
    const ms = Date.now() - new Date(iso).getTime();
    if (ms < 5000) return "just now";
    if (ms < 60_000) return `${Math.floor(ms / 1000)}s ago`;
    if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
    if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
    return new Date(iso).toLocaleDateString();
  } catch { return ""; }
};

const COUNTRY_FLAG = (cc) => {
  if (!cc || cc.length !== 2) return "🌍";
  return String.fromCodePoint(...cc.toUpperCase().split("").map(c => 0x1f1e6 + c.charCodeAt(0) - 65));
};

export const PoolPulse = () => {
  const [events, setEvents] = useState([]);
  const [today, setToday] = useState({ card_spend_usd_cents: 0, pool_delta_usd_cents: 0, purchases: 0 });
  const [flashKey, setFlashKey] = useState(0);
  const prevTopId = useRef(null);

  const load = async () => {
    try {
      const { data } = await api.get("/leaderboard/pulse?limit=8");
      const evs = data.events || [];
      setEvents(evs);
      setToday(data.today || { card_spend_usd_cents: 0, pool_delta_usd_cents: 0, purchases: 0 });
      const topKey = evs[0] ? `${evs[0].user_id}-${evs[0].created_at}` : null;
      if (topKey && topKey !== prevTopId.current) {
        prevTopId.current = topKey;
        setFlashKey(k => k + 1);
      }
    } catch (_) {}
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 6000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="cp-surface p-3 relative overflow-hidden" data-testid="pool-pulse">
      <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ background: "linear-gradient(90deg, #A3E63540, transparent 60%)" }}/>
      <div className="relative flex items-center justify-between gap-3 flex-wrap mb-2">
        <div className="flex items-center gap-2">
          <span className="relative inline-flex">
            <Zap size={14} className="text-cp-lime"/>
            <span className="absolute inset-0 animate-ping opacity-60"><Zap size={14} className="text-cp-lime"/></span>
          </span>
          <span className="text-[10px] uppercase tracking-widest font-bold" style={{ color: "var(--cp-text-muted)" }}>Pool Pulse · Live</span>
        </div>
        <div className="flex gap-4 text-xs">
          <div>
            <span className="opacity-60">Today's card spend: </span>
            <span className="font-bold tabular-nums" data-testid="pulse-today-spend">
              <CountUp target={today.card_spend_usd_cents / 100} prefix="$"/>
            </span>
          </div>
          <div className="border-l pl-3" style={{ borderColor: "var(--cp-border)" }}>
            <span className="opacity-60">Pool grew: </span>
            <span className="text-cp-lime font-extrabold tabular-nums" data-testid="pulse-today-delta">
              <CountUp target={today.pool_delta_usd_cents / 100} prefix="+$"/>
            </span>
            <span className="opacity-50 ml-1">({today.purchases || 0} cards)</span>
          </div>
        </div>
      </div>

      {events.length === 0 ? (
        <div className="relative text-center py-3 text-xs" style={{ color: "var(--cp-text-muted)" }} data-testid="pulse-empty">
          <TrendingUp size={14} className="inline mr-1 opacity-50"/>
          Be the first to buy a card today and fuel the pool.
        </div>
      ) : (
        <ul className="relative space-y-1 max-h-[200px] overflow-y-auto pr-1" data-testid="pulse-feed">
          {events.map((e, i) => (
            <li
              key={`${e.user_id}-${e.created_at}-${i}`}
              className={`flex items-center gap-2 text-xs py-1 px-2 rounded transition ${i === 0 ? "bg-cp-lime/10" : ""}`}
              style={i === 0 ? { animation: `cp-pulse-in 600ms ease-out ${flashKey}` } : {}}
              data-testid={`pulse-event-${i}`}
            >
              <span className="opacity-70" style={{ fontSize: 14 }}>{COUNTRY_FLAG(e.country_code)}</span>
              <span className="font-bold flex-1 truncate">{e.handle}</span>
              <span className="opacity-60 truncate hidden sm:inline">
                bought {e.card_name ? `“${e.card_name}”` : "a card"} for
              </span>
              <span className="tabular-nums font-bold">{USD(e.amount_usd_cents)}</span>
              <span className="text-cp-lime tabular-nums font-extrabold" data-testid={`pulse-delta-${i}`}>
                +{USD(e.pool_delta_usd_cents)}
              </span>
              <span className="opacity-40 text-[10px] w-12 text-right">{TIME_AGO(e.created_at)}</span>
            </li>
          ))}
        </ul>
      )}

      <style>{`
        @keyframes cp-pulse-in {
          0% { transform: translateY(-6px); opacity: 0; background-color: #A3E63540; }
          60% { background-color: #A3E63525; }
          100% { transform: translateY(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
};

export default PoolPulse;
