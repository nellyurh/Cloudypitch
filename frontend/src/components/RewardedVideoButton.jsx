import React, { useState } from "react";
import api from "../lib/api";
import { Gift, AlertTriangle, Check } from "lucide-react";

/**
 * RewardedVideoButton — opt-in. User watches a sponsor ad → claim +5 card uses or +50 prediction points.
 * Backend rate-limits to 1 reward per 60 seconds per user.
 */
export const RewardedVideoButton = ({ rewardType = "card_uses" }) => {
  const [phase, setPhase] = useState("idle"); // idle | watching | claiming | done | error
  const [msg, setMsg] = useState("");

  const start = async () => {
    setPhase("watching");
    setMsg("");
    // Simulated 5-second ad. In production this opens AdMob rewarded SDK.
    setTimeout(async () => {
      setPhase("claiming");
      try {
        const { data } = await api.post("/ads/reward/claim", { reward_type: rewardType });
        setPhase("done");
        if (rewardType === "card_uses") setMsg(`+${data.reward.uses_added} uses added to your top card`);
        else setMsg(`+${data.reward.points_added} bonus points`);
      } catch (e) {
        setPhase("error");
        setMsg(e?.response?.data?.detail || "Reward unavailable");
      }
    }, 5000);
  };

  if (phase === "watching") {
    return (
      <div className="fixed inset-0 z-[170] flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.85)" }} data-testid="rewarded-watching">
        <div className="cp-surface max-w-md w-full p-8 text-center">
          <div className="mb-3 text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>SPONSORED</div>
          <div className="text-2xl font-extrabold mb-3">Watching ad…</div>
          <div className="h-1 rounded overflow-hidden mt-4" style={{ background: "var(--cp-surface-2)" }}>
            <div className="h-1 bg-cp-lime" style={{ animation: "rewardedFill 5s linear forwards" }}/>
          </div>
          <style>{`@keyframes rewardedFill { from { width: 0% } to { width: 100% } }`}</style>
        </div>
      </div>
    );
  }
  return (
    <div data-testid="rewarded-button">
      <button
        onClick={start}
        disabled={phase === "claiming"}
        className="cp-btn-ghost w-full inline-flex items-center justify-center gap-2"
        data-testid="rewarded-start"
      >
        <Gift size={14} className="text-cp-lime"/>
        {rewardType === "card_uses" ? "Watch ad → +5 card uses" : "Watch ad → +50 bonus points"}
      </button>
      {phase === "done" && (
        <div className="text-xs mt-2 inline-flex items-center gap-1 text-cp-lime" data-testid="rewarded-success">
          <Check size={12}/> {msg}
        </div>
      )}
      {phase === "error" && (
        <div className="text-xs mt-2 inline-flex items-center gap-1 text-amber-400" data-testid="rewarded-error">
          <AlertTriangle size={12}/> {msg}
        </div>
      )}
    </div>
  );
};

export default RewardedVideoButton;
