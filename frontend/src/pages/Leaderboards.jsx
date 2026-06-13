import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { Trophy, Users, DollarSign, Sparkles, Crown, X, Check, AlertCircle, ShieldCheck } from "lucide-react";
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
  const [eligibility, setEligibility] = useState(null);
  const [openUser, setOpenUser] = useState(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        if (tab === "referrals") {
          const { data } = await api.get("/referrals/leaderboard?limit=100");
          setRows(data.leaderboard || []);
          const p = data.pool || {};
          setPool({
            base_usd_cents: p.amount_usd_cents || 0,
            cards_cut_usd_cents: 0,
            total_usd_cents: p.amount_usd_cents || 0,
          });
          setEligibility(null);
        } else {
          const { data } = await api.get(`/leaderboard?scope=${tab}&limit=100`);
          setRows(data.leaderboard || []);
          setPool(data.pool || { base_usd_cents: 250000, cards_cut_usd_cents: 0, total_usd_cents: 250000 });
          setEligibility(data.eligibility || null);
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

      {/* Eligibility rule banner */}
      {!isReferrals && eligibility && (
        <div className="cp-surface p-3 flex items-start gap-2 text-xs" data-testid="lb-eligibility-banner" style={{ borderColor: "#A3E635" }}>
          <ShieldCheck size={14} className="text-cp-lime mt-0.5 shrink-0"/>
          <div>
            <div className="font-bold text-cp-lime">Prize Pool Eligibility</div>
            <div className="opacity-80" style={{ color: "var(--cp-text-muted)" }}>{eligibility.rule}</div>
          </div>
        </div>
      )}

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
                className={`px-3 py-2 flex items-center gap-3 text-sm cursor-pointer hover:bg-white/5 transition ${r.rank <= 4 ? "bg-cp-lime/5" : ""}`}
                data-testid={`lb-row-${r.user_id}`}
                onClick={() => !isReferrals && setOpenUser(r.user_id)}
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
                    {!isReferrals && r.is_eligible && (
                      <span className="cp-pill !text-[8px] !font-bold inline-flex items-center gap-0.5" style={{ background: "rgba(163,230,53,0.18)", color: "#A3E635" }} title="Eligible for prize-pool payout">
                        <Check size={9}/> ELIGIBLE
                      </span>
                    )}
                    {!isReferrals && !r.is_eligible && r.total_points > 0 && (
                      <span className="cp-pill !text-[8px] !font-bold inline-flex items-center gap-0.5" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }} title={`Needs ≥${r.min_pred_points || 10} pred AND ≥${r.min_fantasy_points || 10} fantasy points`}>
                        <AlertCircle size={9}/> NOT YET
                      </span>
                    )}
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

      {openUser && <UserDetailModal userId={openUser} onClose={() => setOpenUser(null)}/>}
    </div>
  );
};

function UserDetailModal({ userId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get(`/leaderboard/user/${userId}`);
        if (alive) setData(data);
      } catch (_) { /* noop */ }
      if (alive) setLoading(false);
    })();
    return () => { alive = false; };
  }, [userId]);

  const u = data?.user;
  const totals = data?.totals || {};
  const preds = data?.predictions || [];
  const squad = data?.squad;
  const wcEntries = data?.wc_entries || [];

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/70 backdrop-blur-sm"
      onClick={onClose}
      data-testid="user-detail-modal"
    >
      <div
        className="cp-surface w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between p-3 border-b" style={{ borderColor: "var(--cp-border)", background: "var(--cp-surface)" }}>
          <div className="min-w-0">
            <div className="text-base font-extrabold truncate flex items-center gap-2">
              {u?.display_name || "Player"}
              {u?.is_premium && <Crown size={12} className="text-cp-lime"/>}
              {totals.is_eligible && (
                <span className="cp-pill !text-[9px] !font-bold inline-flex items-center gap-0.5" style={{ background: "rgba(163,230,53,0.18)", color: "#A3E635" }}>
                  <Check size={10}/> ELIGIBLE
                </span>
              )}
            </div>
            <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>{u?.country_code || "—"}</div>
          </div>
          <button onClick={onClose} className="cp-btn-ghost !p-1.5" data-testid="user-detail-close"><X size={16}/></button>
        </div>

        {loading ? (
          <div className="p-8 text-center text-sm" style={{ color: "var(--cp-text-muted)" }}>Loading…</div>
        ) : !u ? (
          <div className="p-8 text-center text-sm" style={{ color: "var(--cp-text-muted)" }}>User not found.</div>
        ) : (
          <div className="p-3 space-y-3">
            {/* Totals breakdown */}
            <div className="grid grid-cols-4 gap-2 text-center">
              <Stat label="Total" value={totals.total_points} highlight/>
              <Stat label="Predictions" value={totals.prediction_points}/>
              <Stat label="Fantasy" value={totals.fantasy_points}/>
              <Stat label="WC Mini" value={totals.wc_fantasy_points}/>
            </div>
            {!totals.is_eligible && (
              <div className="cp-surface p-2 text-[11px] flex items-start gap-2" style={{ borderColor: "#FBBF24" }} data-testid="user-detail-ineligible">
                <AlertCircle size={12} className="mt-0.5 shrink-0" style={{ color: "#FBBF24" }}/>
                <span>Not yet eligible for prize-pool payout — needs ≥ {totals.min_prediction_points} prediction points AND ≥ {totals.min_fantasy_points} fantasy points (main + WC mini combined).</span>
              </div>
            )}

            {/* Main squad */}
            {squad && (
              <div>
                <div className="text-[10px] uppercase tracking-widest mb-1.5" style={{ color: "var(--cp-text-muted)" }}>Main Squad — {squad.squad_name || "Unnamed"}</div>
                <div className="cp-surface p-2 grid grid-cols-3 gap-2 text-xs">
                  <div><span className="opacity-60">Players </span><span className="font-bold">{(squad.players || []).length || 15}</span></div>
                  <div><span className="opacity-60">Spent </span><span className="font-bold tabular-nums">€{((squad.budget_spent || 0) / 1_000_000).toFixed(1)}M</span></div>
                  <div><span className="opacity-60">Points </span><span className="font-bold text-cp-lime tabular-nums">{squad.total_points || 0}</span></div>
                </div>
              </div>
            )}

            {/* Predictions */}
            {preds.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-widest mb-1.5" style={{ color: "var(--cp-text-muted)" }}>Predictions ({preds.length})</div>
                <div className="cp-surface divide-y" style={{ borderColor: "var(--cp-border)" }}>
                  {preds.slice(0, 20).map(p => {
                    const m = p.match || {};
                    const settled = !!p.settled_at;
                    const exact = !!p.exact_score_hit;
                    const ok = !!p.outcome_correct;
                    return (
                      <div key={p.id} className="px-2 py-1.5 flex items-center gap-2 text-xs" data-testid={`user-detail-pred-${p.match_id}`}>
                        <div className="flex-1 min-w-0 truncate">
                          {(m.home_team_name || "—")} vs {(m.away_team_name || "—")}
                        </div>
                        <div className="tabular-nums opacity-70">{p.home_score_predicted}–{p.away_score_predicted}</div>
                        {settled && (m.home_score != null) && (
                          <div className="tabular-nums text-[10px] opacity-50">→ {m.home_score}–{m.away_score}</div>
                        )}
                        <div className="text-right tabular-nums font-bold" style={{ color: exact ? "#A3E635" : ok ? "#FBBF24" : settled ? "#FF3D52" : "var(--cp-text-muted)" }}>
                          {settled ? `+${p.points_awarded || 0}` : "—"}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* WC mini-game entries */}
            {wcEntries.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-widest mb-1.5" style={{ color: "var(--cp-text-muted)" }}>WC Mini-Game Entries ({wcEntries.length})</div>
                <div className="cp-surface divide-y" style={{ borderColor: "var(--cp-border)" }}>
                  {wcEntries.slice(0, 20).map(e => (
                    <div key={e.id} className="px-2 py-1.5 flex items-center gap-2 text-xs" data-testid={`user-detail-wc-${e.wc_game_id}`}>
                      <div className="flex-1 min-w-0 truncate">{e.wc_game?.title || e.wc_game?.game_type || "Mini-game"}</div>
                      <div className="text-[10px] opacity-60">{(e.player_picks || []).length} picks</div>
                      <div className="text-right tabular-nums font-bold text-cp-lime">+{e.points_scored || 0}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {preds.length === 0 && !squad && wcEntries.length === 0 && (
              <div className="text-center text-sm py-6" style={{ color: "var(--cp-text-muted)" }}>This user hasn&apos;t played yet.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, highlight }) {
  return (
    <div className="cp-surface p-2">
      <div className="text-[9px] uppercase opacity-60">{label}</div>
      <div className={`text-base font-extrabold tabular-nums ${highlight ? "text-cp-lime" : ""}`}>{value || 0}</div>
    </div>
  );
}

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
