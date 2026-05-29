import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Link } from "react-router-dom";
import { Users, Copy, Check, Trophy, Share2, Coins } from "lucide-react";

const fmtUsd = (cents) => `$${((cents || 0) / 100).toFixed(2)}`;

export const ReferralsPage = () => {
  const { user } = useAuth();
  const [me, setMe] = useState(null);
  const [board, setBoard] = useState([]);
  const [pool, setPool] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [m, lb] = await Promise.all([
          user ? api.get("/referrals/me") : Promise.resolve({ data: null }),
          api.get("/referrals/leaderboard"),
        ]);
        if (m.data) setMe(m.data);
        setBoard(lb.data.leaderboard || []);
        setPool(lb.data.pool || null);
      } catch (_) {}
    })();
  }, [user]);

  const shareUrl = me?.referral_code
    ? `${window.location.origin}/signup?ref=${me.referral_code}`
    : null;

  const copy = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch (_) {}
  };

  const share = async () => {
    if (!shareUrl) return;
    if (navigator.share) {
      try {
        await navigator.share({
          title: "Join me on Cloudy Pitch",
          text: `Predict the FIFA World Cup 2026 with me on Cloudy Pitch — bonus card on signup!`,
          url: shareUrl,
        });
      } catch (_) {}
    } else {
      copy();
    }
  };

  return (
    <div data-testid="referrals-page">
      <div
        className="relative overflow-hidden rounded-xl"
        style={{ background: "linear-gradient(135deg, #064E3B 0%, #1A1F26 100%)" }}
      >
        <div className="px-6 md:px-10 py-8 md:py-12 text-white">
          <div className="inline-flex items-center gap-2 cp-pill" style={{ background: "rgba(163,230,53,0.2)", color: "#A3E635" }}>
            <Users size={12}/> REFERRAL CHAMPIONS POOL
          </div>
          <h1 className="text-3xl md:text-5xl font-extrabold mt-3 tracking-tight">
            Invite friends.<br/><span className="text-cp-lime">Win the side pool.</span>
          </h1>
          <p className="text-sm md:text-base mt-3 max-w-lg" style={{ color: "rgba(255,255,255,0.85)" }}>
            Every time someone uses your code, you climb the Referral Leaderboard.
            Every dollar your friends spend on Legend Cards earns you a credit.
            Top referrers split the <span className="text-cp-lime font-bold">{pool ? fmtUsd(pool.amount_usd_cents) : "$5,000"}</span> prize pool.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 mt-4">
        <div>
          {/* Share card */}
          {user ? (
            <div className="cp-surface p-5" data-testid="my-referral-code">
              <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Your Referral Code</div>
              <div className="flex items-center gap-2 mt-1">
                <code className="font-extrabold text-2xl tracking-widest text-cp-lime tabular-nums" data-testid="referral-code">{me?.referral_code || "…"}</code>
                <button onClick={copy} className="cp-btn-ghost !py-1 !px-2 text-xs inline-flex items-center gap-1" data-testid="copy-code">
                  {copied ? <><Check size={12}/> Copied</> : <><Copy size={12}/> Copy code</>}
                </button>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <input
                  readOnly
                  value={shareUrl || ""}
                  className="cp-input flex-1 text-xs"
                  data-testid="referral-link"
                />
                <button onClick={copy} className="cp-btn-ghost text-xs inline-flex items-center gap-1" data-testid="copy-link">
                  <Copy size={12}/> Copy
                </button>
                <button onClick={share} className="cp-btn-primary text-xs inline-flex items-center gap-1" data-testid="share-link">
                  <Share2 size={12}/> Share
                </button>
              </div>

              <div className="grid grid-cols-4 gap-3 mt-5 text-center">
                <div>
                  <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Invited</div>
                  <div className="text-2xl font-extrabold tabular-nums">{me?.count || 0}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Active</div>
                  <div className="text-2xl font-extrabold tabular-nums text-cp-lime">{me?.active_count || 0}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Their Spend</div>
                  <div className="text-lg font-bold tabular-nums">{fmtUsd(me?.total_referred_spend_usd_cents)}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Credit</div>
                  <div className="text-lg font-bold tabular-nums text-cp-lime">{fmtUsd(me?.total_credits_usd_cents)}</div>
                </div>
              </div>
            </div>
          ) : (
            <div className="cp-surface p-6 text-center">
              <Users size={36} className="mx-auto text-cp-lime opacity-60"/>
              <p className="text-sm mt-3 mb-3" style={{ color: "var(--cp-text-muted)" }}>Sign in to get your referral code.</p>
              <Link to="/signin" className="cp-btn-primary" data-testid="referrals-signin">Sign in</Link>
            </div>
          )}

          {/* My referrals list */}
          {user && (me?.referrals || []).length > 0 && (
            <div className="cp-surface mt-3 overflow-hidden">
              <div className="cp-card-header normal-case"><span className="font-bold">My Invites</span></div>
              <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
                {me.referrals.map(r => (
                  <li key={r.id} className="px-3 py-2 flex items-center justify-between text-sm" data-testid={`my-referral-${r.id}`}>
                    <div>
                      <div className="font-medium">{r.referred_display_name}</div>
                      <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
                        Joined {r.referred_joined_at ? new Date(r.referred_joined_at).toLocaleDateString() : "—"} ·
                        {r.status === "active" ? " active" : " pending"}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold tabular-nums text-cp-lime">{fmtUsd(r.credit_earned_usd_cents)}</div>
                      <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>credit earned</div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* How it works */}
          <div className="cp-surface mt-3 p-5">
            <h3 className="text-sm font-extrabold uppercase tracking-widest mb-3" style={{ color: "var(--cp-text-muted)" }}>How It Works</h3>
            <ol className="space-y-2 text-sm">
              <li className="flex gap-3"><span className="cp-pill !w-6 !h-6 !p-0 flex items-center justify-center text-cp-lime font-extrabold">1</span> <span>Share your code or link with friends.</span></li>
              <li className="flex gap-3"><span className="cp-pill !w-6 !h-6 !p-0 flex items-center justify-center text-cp-lime font-extrabold">2</span> <span>They sign up using your code and get a free starter card pack.</span></li>
              <li className="flex gap-3"><span className="cp-pill !w-6 !h-6 !p-0 flex items-center justify-center text-cp-lime font-extrabold">3</span> <span>You earn a credit equal to 10% of every dollar they spend on Legend Cards.</span></li>
              <li className="flex gap-3"><span className="cp-pill !w-6 !h-6 !p-0 flex items-center justify-center text-cp-lime font-extrabold">4</span> <span>Top of the referral leaderboard on tournament close splits the prize pool.</span></li>
            </ol>
          </div>
        </div>

        {/* Leaderboard sidebar */}
        <aside className="cp-surface h-fit lg:sticky lg:top-[110px] overflow-hidden" data-testid="referral-leaderboard">
          <div className="cp-card-header normal-case">
            <span className="flex items-center gap-2 font-bold" style={{ color: "var(--cp-text)" }}>
              <Trophy size={14} className="text-cp-lime"/> Top Referrers
            </span>
          </div>
          <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
            {board.length === 0 && (
              <li className="p-4 text-sm" style={{ color: "var(--cp-text-muted)" }}>
                Be the first — share your code now.
              </li>
            )}
            {board.map(r => (
              <li
                key={r.user_id}
                className={`px-3 py-2 flex items-center gap-2 text-sm ${user && r.user_id === user.id ? "bg-cp-lime/10" : ""}`}
              >
                <span
                  className="cp-logo-circle text-[10px] font-extrabold shrink-0"
                  style={{
                    width: 22, height: 22,
                    background: r.rank === 1 ? "#A3E635" : "var(--cp-surface-2)",
                    color: r.rank === 1 ? "#064E3B" : "var(--cp-text)",
                  }}
                >
                  {r.rank}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="truncate font-medium">{r.display_name}</div>
                  <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
                    {r.referred_count} invited · {r.active_count} active
                  </div>
                </div>
                <span className="tabular-nums font-bold text-cp-lime text-xs">{fmtUsd(r.total_credits_usd_cents)}</span>
              </li>
            ))}
          </ul>
          {pool && (
            <div className="p-3 border-t" style={{ borderColor: "var(--cp-border)" }}>
              <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>Prize Pool</div>
              <div className="text-xl font-extrabold text-cp-lime tabular-nums">{fmtUsd(pool.amount_usd_cents)}</div>
              <div className="text-[10px] mt-1 inline-flex items-center gap-1" style={{ color: "var(--cp-text-muted)" }}>
                <Coins size={10}/> Growing with every card purchase
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
};

export default ReferralsPage;
