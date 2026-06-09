import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";
import api from "../lib/api";
import LegendCardArt from "./LegendCardArt";

const TIER_FROM_NUM = { 1: "gold", 2: "elite", 3: "epic" };
const TIER_LABEL = { 1: "GOAT", 2: "ELITE", 3: "STAR" };

/**
 * Once-per-session, on auth-ready, ask the backend whether the user qualifies
 * for the matchday-completion drop. If yes, surface a celebratory toast that
 * showcases the new card. Backend already prevents duplicate drops via the
 * `card_drops_log` collection.
 */
export const DailyDropWatcher = () => {
  const { user } = useAuth();
  const fired = useRef(false);

  useEffect(() => {
    if (!user || fired.current) return;
    fired.current = true;
    (async () => {
      try {
        const { data } = await api.post("/cards/daily-drop");
        if (!data?.dropped || !data.card) return;
        const tier = TIER_FROM_NUM[data.card.tier] || "epic";
        const isFinal = data.is_final_day_drop;
        toast.custom(
          () => (
            <div
              className="flex items-center gap-3 p-3 rounded-xl"
              style={{
                background: "linear-gradient(135deg, #0F2A1F 0%, #051711 100%)",
                border: "1px solid var(--cp-border)",
                boxShadow: "0 18px 40px rgba(0,0,0,0.6)",
                minWidth: 320,
              }}
              data-testid="daily-drop-toast"
            >
              <LegendCardArt
                tier={tier}
                title={data.card.player_name || data.card.name || TIER_LABEL[data.card.tier]}
                size={92}
              />
              <div className="text-sm text-white">
                <div className="font-extrabold text-base" style={{ color: "var(--cp-lime)" }}>
                  {isFinal && data.card.tier === 1 ? "🏆 Final-Day GOLD drop!" : "Matchday Reward!"}
                </div>
                <div className="opacity-90 mt-0.5">
                  You earned a <b>{TIER_LABEL[data.card.tier]}</b> Legend Card
                </div>
                <div className="opacity-75 text-xs mt-0.5">
                  {data.card.uses_granted} uses · {data.card.name || ""}
                </div>
              </div>
            </div>
          ),
          { duration: 9000, position: "top-center" }
        );
      } catch (_) {
        // Silent — user might not be eligible / endpoint may transiently fail.
      }
    })();
  }, [user]);

  return null;
};

export default DailyDropWatcher;
