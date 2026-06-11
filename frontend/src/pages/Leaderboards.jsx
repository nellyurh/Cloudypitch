import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { Trophy, Users, DollarSign, Sparkles, Crown } from "lucide-react";
import PoolPulse from "../components/PoolPulse";
import { useCurrency } from "../lib/currency";

const USD = (cents) => `$${((cents || 0) / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Currency-aware formatter used inside components via useCurrency()
function formatPrize(cents, cur) {
  if (!cur) return USD(cents);
  return cur.formatCents(cents);
}

const TABS = [
  { k: "global",   l: "Global",   icon: Trophy },
  { k: "weekly",   l: "Weekly",   icon: Sparkles },
  { k: "premium",  l: "Premium",  icon: Crown },
  { k: "referrals",l: "Referrals",icon: Users },
];

export const Leaderboards = () => {
  const [tab, setTab] = useState("global");
  const [rows, setRows] = useState([]);
  const [pool, setPool] = useState({ base_usd_cents: 250000, cards_cut_usd_cents: 0, total_usd_cents: 250000 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        if (tab === "referrals") {
          const { data } = await api.get("/referrals/leaderboard?limit=100");
          setRows(data.leaderboard || []);
          // Referrals pool comes back as the full prize-pool doc (may be null) — use amount_usd_cents
          const p = data.pool || {};
          setPool({
            base_usd_cents: p.amount_usd_cents || 0,
            cards_cut_usd_cents: 0,
            total_usd_cents: p.amount_usd_cents || 0,
          });
        } else {
          const { data } = await api.get(`/leaderboard?scope=${tab}&limit=100`);
          setRows(data.leaderboard || []);
          setPool(data.pool || { base_usd_cents: 250000, cards_cut_usd_cents: 0, total_usd_cents: 250000 });
        }
      } catch (_) {
        setRows([]);
      }
      setLoading(false);
    })();
  }, [tab]);

  const isReferrals = tab === "referrals";

  return (
    <div data-testid="leaderboards-page" className="space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-xl sm:text-2xl font-extrabold">Leaderboards</h1>
        <div className="flex gap-1 cp-surface p-1 overflow-x-auto max-w-full no-scrollbar" data-testid="lb-tabs">
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <button
                key={t.k}
                onClick={() => setTab(t.k)}
                className={`px-2.5 sm:px-3 py-1.5 text-xs sm:text-sm rounded transition flex items-center gap-1.5 shrink-0 ${tab === t.k ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`}
                data-testid={`lb-tab-${t.k}`}
              >
                <Icon size={12}/> {t.l}
              </button>
            );
          })}
        </div>
      </div>

      {/* Prize pool header */}
      <PrizePoolCard pool={pool} isReferrals={isReferrals}/>

      {/* Distribution breakdown */}
      {!isReferrals && <PrizeBreakdown pool={pool}/>}

      {/* Pool Pulse — live feed of card purchases */}
      {!isReferrals && <PoolPulse/>}

      <div className="cp-surface overflow-hidden">
        {loading && <div className="p-6 text-sm" style={{ color: "var(--cp-text-muted)" }} data-testid="lb-loading">Loading…</div>}
        {!loading && rows.length === 0 && <div className="p-6 text-sm" style={{ color: "var(--cp-text-muted)" }} data-testid="lb-empty">No leaderboard data yet.</div>}
        {!loading && rows.length > 0 && (
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {rows.map(r => (
              <li
                key={r.user_id}
                className={`px-3 py-2 flex items-center gap-3 text-sm ${r.rank <= 4 ? "bg-cp-lime/5" : ""}`}
                data-testid={`lb-row-${r.user_id}`}
              >
                <span
                  className="cp-logo-circle text-[10px] shrink-0"
                  style={{
                    width: 28, height: 28,
                    background: r.rank === 1 ? "#FBBF24" : r.rank === 2 ? "#CBD5E1" : r.rank === 3 ? "#FB923C" : r.rank <= 4 ? "#A3E635" : "var(--cp-surface-2)",
                    color: r.rank <= 4 ? "#064E3B" : "var(--cp-text)",
                    fontWeight: 800,
                  }}
                >
                  {r.rank}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="truncate font-medium flex items-center gap-1.5">
                    {r.display_name || "Player"}
                    {r.is_premium && <Crown size={11} className="text-cp-lime"/>}
                  </div>
                  <div className="text-[10px] flex items-center gap-1.5" style={{ color: "var(--cp-text-muted)" }}>
                    <span>{r.country_code || "—"}</span>
                    {!isReferrals && (
                      <>
                        <span>·</span>
                        <span>Pred {r.prediction_points || 0}</span>
                        <span>·</span>
                        <span>Fan {(r.fantasy_points || 0) + (r.wc_fantasy_points || 0)}</span>
                      </>
                    )}
                    {isReferrals && (
                      <>
                        <span>·</span>
                        <span>{r.referred_count || 0} referrals</span>
                        {r.active_count > 0 && (<><span>·</span><span>{r.active_count} active</span></>)}
                      </>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  {isReferrals ? (
                    <>
                      <div className="text-cp-lime font-extrabold tabular-nums" data-testid={`lb-points-${r.user_id}`}>
                        {USD(r.total_credits_usd_cents)}
                      </div>
                      <div className="text-[10px] opacity-60">earned</div>
                    </>
                  ) : (
                    <>
                      <div className="text-cp-lime font-extrabold tabular-nums" data-testid={`lb-points-${r.user_id}`}>
                        {r.total_points || 0}<span className="text-[9px] uppercase ml-0.5 opacity-60">pts</span>
                      </div>
                      {r.potential_prize_usd_cents > 0 && (
                        <div className="text-[10px] tabular-nums" style={{ color: "var(--cp-text-muted)" }} data-testid={`lb-prize-${r.user_id}`}>
                          <DollarSign size={9} className="inline -mt-0.5"/>{USD(r.potential_prize_usd_cents).replace("$", "")}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {!isReferrals && (
        <div className="text-[10px] text-center" style={{ color: "var(--cp-text-muted)" }} data-testid="lb-note">
          Positions 21+ start earning prize once players spend on Legend Cards. 50% of every card purchase fuels the pool.
        </div>
      )}
    </div>
  );
};

function PrizePoolCard({ pool, isReferrals }) {
  const cur = useCurrency();
  const base = pool.base_usd_cents || 0;
  const cardsCut = pool.cards_cut_usd_cents || 0;
  const total = pool.total_usd_cents || (base + cardsCut);
  return (
    <div className="cp-surface p-4 relative overflow-hidden" data-testid="lb-pool-card">
      <div className="absolute inset-0 opacity-10" style={{ background: "radial-gradient(circle at 20% 0%, #A3E63540, transparent 60%)" }}/>
      <div className="relative flex items-center gap-4 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>
            {isReferrals ? "Referral Prize Pool" : "Cloudy Pitch Prize Pool"}
          </div>
          <div className="text-3xl font-extrabold text-cp-lime tabular-nums" data-testid="lb-pool-total">
            {USD(total)}
          </div>
        </div>
        {!isReferrals && (
          <div className="flex gap-4 text-sm">
            <div>
              <div className="text-[10px] uppercase" style={{ color: "var(--cp-text-muted)" }}>Base</div>
              <div className="font-bold tabular-nums" data-testid="lb-pool-base">{USD(base)}</div>
            </div>
            <div className="border-l pl-4" style={{ borderColor: "var(--cp-border)" }}>
              <div className="text-[10px] uppercase" style={{ color: "var(--cp-text-muted)" }}>Cards Cut <span className="opacity-60">(50%)</span></div>
              <div className="font-bold tabular-nums" data-testid="lb-pool-cards">{USD(cardsCut)}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function PrizeBreakdown({ pool }) {
  // On phones the 7-tier grid is too tall, so collapse it behind a tap.
  // Default-open on ≥sm so desktop users see it at a glance; default-closed
  // on phones so the leaderboard stays the focus.
  const [open, setOpen] = React.useState(() => {
    if (typeof window === "undefined") return true;
    return window.innerWidth >= 640;
  });
  const base = pool.base_usd_cents || 0;
  const cardsCut = pool.cards_cut_usd_cents || 0;
  // Mirror backend compute_prize_split for the headline tiers.
  // Each tier carries TWO numbers: the original base distribution and the
  // live bonus from card revenue. The user explicitly asked to surface
  // both so the original payout structure they configured is always
  // visible alongside any prize-pool growth.
  const BASE_REF = 250000;
  const f = base / BASE_REF;
  const base_top4 = [100000 * f, 50000 * f, 30000 * f, 20000 * f];
  const base_rem = Math.max(0, base - base_top4.reduce((a, b) => a + b, 0));
  const base_pos5_20 = base_rem / 16;
  const cc_top4 = (cardsCut / 4) / 4;
  const cc_5_15 = (cardsCut / 4) / 11;
  const cc_16_100 = (cardsCut / 2) / 85;

  const tiers = [
    { rank: "1st",    base: base_top4[0], bonus: cc_top4 },
    { rank: "2nd",    base: base_top4[1], bonus: cc_top4 },
    { rank: "3rd",    base: base_top4[2], bonus: cc_top4 },
    { rank: "4th",    base: base_top4[3], bonus: cc_top4 },
    { rank: "5–15",   base: base_pos5_20, bonus: cc_5_15,  perPos: true },
    { rank: "16–20",  base: base_pos5_20, bonus: cc_16_100, perPos: true },
    { rank: "21–100", base: 0,            bonus: cc_16_100, perPos: true, conditional: cardsCut === 0 },
  ];
  return (
    <div className="cp-surface p-3" data-testid="lb-breakdown">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between mb-2"
        data-testid="lb-breakdown-toggle"
        aria-expanded={open}
      >
        <div className="text-[10px] uppercase tracking-widest text-left" style={{ color: "var(--cp-text-muted)" }}>Prize Distribution</div>
        <div className="flex items-center gap-3">
          <div className="text-[9px] hidden sm:flex items-center gap-2" style={{ color: "var(--cp-text-muted)" }}>
            <span className="inline-flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full" style={{background: "#A3E635"}}/>Base</span>
            {cardsCut > 0 && <span className="inline-flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full" style={{background: "#F5A623"}}/>Cards bonus</span>}
          </div>
          <span className="text-cp-lime text-base leading-none" aria-hidden="true">{open ? "▾" : "▸"}</span>
        </div>
      </button>
      {!open && (
        <div className="text-[10px] sm:hidden" style={{ color: "var(--cp-text-muted)" }}>
          Tap to see 1st–100th payouts (Base + Cards bonus split).
        </div>
      )}
      {open && (
        <>
          <div className="text-[9px] flex sm:hidden items-center gap-2 mb-2" style={{ color: "var(--cp-text-muted)" }}>
            <span className="inline-flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full" style={{background: "#A3E635"}}/>Base</span>
            {cardsCut > 0 && <span className="inline-flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full" style={{background: "#F5A623"}}/>Cards bonus</span>}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
        {tiers.map(t => {
          const total = t.base + t.bonus;
          return (
            <div
              key={t.rank}
              className={`rounded p-2 text-center ${t.conditional ? "opacity-50" : ""}`}
              style={{ background: "var(--cp-surface-2)" }}
              data-testid={`lb-tier-${t.rank}`}
            >
              <div className="text-[10px] font-bold" style={{ color: "var(--cp-text-muted)" }}>{t.rank}</div>
              <div className="text-sm font-extrabold text-cp-lime tabular-nums" data-testid={`lb-tier-amt-${t.rank}`}>
                {USD(Math.round(total))}
              </div>
              {t.base > 0 && (
                <div className="text-[9px] opacity-70 tabular-nums">
                  <span style={{ color: "#A3E635" }}>{USD(Math.round(t.base))}</span>
                  {t.bonus > 0 && (
                    <>
                      <span className="opacity-50"> + </span>
                      <span style={{ color: "#F5A623" }}>{USD(Math.round(t.bonus))}</span>
                    </>
                  )}
                </div>
              )}
              {t.perPos && <div className="text-[9px] opacity-60">per position</div>}
              {t.conditional && <div className="text-[9px] opacity-60">unlocks via cards</div>}
            </div>
          );
        })}
          </div>
        </>
      )}
    </div>
  );
}

export default Leaderboards;
