import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { Trophy, Plus, ArrowRight, Star, Repeat, Coins } from "lucide-react";

const fmt = (n) => `€${(n || 0).toFixed(1)}M`;

export default function MyTeams() {
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [transfers, setTransfers] = useState(null);

  const loadAll = async () => {
    try {
      const [t, tr] = await Promise.all([
        api.get("/fantasy/my-teams"),
        api.get("/fantasy/transfers"),
      ]);
      setTeams(t.data.teams || []);
      setTransfers(tr.data);
    } catch (_) {}
    setLoading(false);
  };
  useEffect(() => { loadAll(); }, []);

  const buyTransferCard = async () => {
    try {
      const { data } = await api.post("/fantasy/transfers/buy");
      alert(`✓ Transfer pack bought. You now have ${data.remaining} transfers.`);
      loadAll();
    } catch (e) {
      alert(`✗ ${e?.response?.data?.detail || e.message}`);
    }
  };

  return (
    <div className="max-w-[1100px] mx-auto p-3 md:p-5" data-testid="my-teams-page">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <h1 className="text-xl md:text-2xl font-extrabold">My Teams</h1>
        <Link
          to="/fantasy"
          className="rounded px-3 py-2 text-xs font-extrabold flex items-center gap-2"
          style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}
          data-testid="create-new-team"
        >
          <Plus size={14}/> New squad
        </Link>
      </div>

      {/* Transfer card panel */}
      {transfers && (
        <div className="cp-surface p-3 mb-4 flex items-center gap-3 flex-wrap" data-testid="transfer-panel">
          <div className="flex items-center gap-2 flex-1 min-w-[200px]">
            <Repeat size={18} className="text-cp-lime"/>
            <div>
              <div className="text-xs font-bold">Transfers: <span className="text-cp-lime tabular-nums">{transfers.remaining}</span> remaining</div>
              <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
                Used across all your squads · 1 transfer = 1 player swap. Out? Buy a pack or take a −{transfers.point_penalty_per_transfer}pt hit per swap.
              </div>
            </div>
          </div>
          <button
            onClick={buyTransferCard}
            className="rounded px-3 py-2 text-xs font-extrabold flex items-center gap-1.5"
            style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}
            data-testid="buy-transfer-pack"
          >
            <Coins size={12}/> ${(transfers.card_price_usd_cents / 100).toFixed(2)} · +{transfers.card_uses} transfers
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-sm opacity-60 p-6 text-center">Loading…</div>
      ) : teams.length === 0 ? (
        <div className="cp-surface p-8 text-center" data-testid="my-teams-empty">
          <Trophy size={36} className="mx-auto opacity-50 mb-3"/>
          <h2 className="font-extrabold text-lg mb-1">No squads yet</h2>
          <p className="text-sm opacity-60 mb-4">Start by building your first World Cup squad. It only takes a minute.</p>
          <Link to="/fantasy" className="inline-block rounded px-4 py-2 font-extrabold" style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}>
            Build a team →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {teams.map(t => (
            <Link
              key={t.id}
              to={
                t.kind === "wc_game" && t.wc_game_id
                  ? `/wc/games/${t.wc_game_id}`
                  : t.game_id
                  ? `/fantasy?game_id=${t.game_id}`
                  : "/build-team"
              }
              className="cp-surface p-4 hover:bg-white/5 transition flex flex-col gap-2"
              data-testid={`my-team-${t.id}`}
            >
              <div className="flex items-center justify-between">
                <h3 className="font-extrabold truncate flex-1">{t.squad_name || "My Squad"}</h3>
                <ArrowRight size={14} className="opacity-60"/>
              </div>
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>
                {t.kind === "wc_game" ? (
                  <span className="cp-pill !text-[9px] !bg-amber-500/20 !text-amber-300 !font-extrabold">Mini-game</span>
                ) : (
                  <span className="cp-pill !text-[9px] !bg-cp-lime/20 !text-cp-lime !font-extrabold">Main</span>
                )}
                <span className="truncate">{t.game_title || t.competition_id || "WC 2026 Fantasy"}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center mt-1">
                <div>
                  <div className="text-[9px] uppercase opacity-60">Players</div>
                  <div className="font-extrabold">{t.player_count}/{(t.players || []).length >= 16 ? "20" : "15"}</div>
                </div>
                <div>
                  <div className="text-[9px] uppercase opacity-60">Spent</div>
                  <div className="font-extrabold">{fmt(t.total_cost)}</div>
                </div>
                <div>
                  <div className="text-[9px] uppercase opacity-60">Points</div>
                  <div className="font-extrabold text-cp-lime">{t.total_points || 0}</div>
                </div>
              </div>
              {(t.captain_id || t.bench_boost) && (
                <div className="flex items-center gap-2 text-[10px] mt-1 pt-1.5 border-t" style={{ borderColor: "var(--cp-border)" }}>
                  {t.captain_id && (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-bold" style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}>
                      <Star size={9}/> Captain set
                    </span>
                  )}
                  {t.bench_boost && (
                    <span className="px-1.5 py-0.5 rounded font-bold bg-amber-400 text-cp-forest">Bench Boost</span>
                  )}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
