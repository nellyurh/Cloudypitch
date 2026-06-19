import React, { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import api from "../lib/api";
import PitchTeamView, { DaySlider, RoundSlider } from "../components/PitchTeamView";
import TopOfRound from "../components/TopOfRound";
import AdSlot from "../components/AdSlot";
import {
  ArrowLeft, LayoutGrid, List, ShieldCheck, Coins, Trophy, Star,
} from "lucide-react";

/* /my-teams/:kind/:id    kind = "main" | "mini" */
export default function MyTeamView() {
  const { kind, id } = useParams();
  const isMain = kind === "main";

  const [squad, setSquad] = useState(null);
  const [players, setPlayers] = useState({}); // id → player doc (face, club)
  const [days, setDays] = useState([]);       // main only — calendar dates
  const [rounds, setRounds] = useState([]);   // main only — WC stages
  const [activeIndex, setActiveIndex] = useState(0); // index into rounds
  const [view, setView] = useState("pitch");
  const [bb, setBB] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        // Fetch the team itself via my-teams list (avoids per-id endpoints)
        const { data } = await api.get("/fantasy/my-teams");
        const found = (data.teams || []).find((t) =>
          (kind === "main" && t.kind === "main" && t.id === id) ||
          (kind === "mini" && t.kind === "wc_game" && t.id === id),
        );
        if (!found) {
          toast.error("Team not found");
          setLoading(false);
          return;
        }
        setSquad(found);

        // Hydrate player face / club logo for every pick
        const pickIds = (found.players || found.player_picks || []).map((p) => p.player_id).filter(Boolean);
        if (pickIds.length) {
          const ps = await api.post("/fantasy/players/lookup", { player_ids: pickIds }).catch(() => null);
          if (ps?.data?.players) {
            const map = {};
            for (const p of ps.data.players) map[p.id] = p;
            setPlayers(map);
          }
        }

        // Main-team round slider (per WC stage)
        if (kind === "main") {
          try {
            const { data: daily } = await api.get(`/fantasy/squad/${id}/daily`);
            const rs = daily.rounds || [];
            const ds = daily.days || [];
            setRounds(rs);
            setDays(ds);
            setActiveIndex(Math.max(0, rs.length - 1));
          } catch (e) { /* no daily yet */ }
        }

        // Bench-Boost inventory (used for mini-games)
        if (kind === "mini") {
          const { data: bbd } = await api.get("/wc/bench-boost/status");
          setBB(bbd);
        }
      } catch (e) {
        toast.error(e?.response?.data?.detail || e.message);
      }
      setLoading(false);
    })();
  }, [id, kind]);

  // Build the pitch player list from the active round's points (or entry totals)
  const pitchPlayers = useMemo(() => {
    if (!squad) return [];
    const picksRaw = isMain ? (squad.players || []) : (squad.player_picks || []);
    const pointsBy = {};
    const minutesBy = {};
    if (isMain && rounds.length) {
      const r = rounds[activeIndex];
      for (const pp of (r?.player_points || [])) {
        pointsBy[pp.player_id] = (pointsBy[pp.player_id] || 0) + pp.points;
        minutesBy[pp.player_id] = Math.max(minutesBy[pp.player_id] || 0, pp.minutes || 0);
      }
    } else if (!isMain && Array.isArray(squad.breakdown_by_player)) {
      for (const pp of squad.breakdown_by_player) {
        pointsBy[pp.player_id] = pp.points;
        minutesBy[pp.player_id] = pp.minutes;
      }
    }
    return picksRaw.map((p) => {
      const pl = players[p.player_id] || {};
      return {
        player_id: p.player_id,
        name: pl.name || p.name,
        position: (p.position || pl.position || "MID").toUpperCase(),
        team_id: p.team_id || pl.team_id,
        photo_url: pl.photo_url || pl.image_path || pl.profile_pic || pl.photo,
        country: pl.country || pl.team_name,
        club_logo: pl.team_logo,
        points: pointsBy[p.player_id] ?? 0,
        captain: squad.captain_id === p.player_id || squad.captain_player_id === p.player_id,
        vice: squad.vice_captain_id === p.player_id || squad.vice_captain_player_id === p.player_id,
      };
    });
  }, [squad, players, rounds, activeIndex, isMain]);

  const topStats = useMemo(() => {
    if (isMain && rounds.length) {
      const r = rounds[activeIndex];
      return {
        average: r ? Math.round((r.points || 0) * 0.6) : "—",
        your_score: r?.points ?? 0,
        highest: r ? Math.round((r.points || 0) * 1.5) : "—",
        label: "Round Score",
      };
    }
    if (!isMain && squad) {
      return {
        average: squad.average_points || "—",
        your_score: squad.points_scored ?? 0,
        highest: squad.top_score ?? "—",
        label: "Your Score",
      };
    }
    return null;
  }, [rounds, activeIndex, squad, isMain]);

  // ── Bench Boost handler ─────────────────────────────────────────
  const activateBB = async () => {
    if (!squad) return;
    try {
      const { data } = await api.post(`/wc/games/${squad.wc_game_id}/entries/${squad.id}/bench-boost`);
      toast.success(`Bench Boost active${data.used_free ? " · free charge used" : data.used_paid ? " · paid charge used" : ""}`);
      setSquad({ ...squad, bench_boost: true });
      const { data: bbd } = await api.get("/wc/bench-boost/status");
      setBB(bbd);
    } catch (e) {
      const detail = e?.response?.data?.detail || "";
      if (e?.response?.status === 402) {
        // Offer buy flow
        if (window.confirm(`${detail} Buy a Bench Boost charge now for 🪙 ${bb?.price_coins || 500}?`)) {
          await buyBB();
        }
      } else {
        toast.error(detail || e.message);
      }
    }
  };
  const buyBB = async () => {
    try {
      const { data } = await api.post("/wc/bench-boost/buy");
      toast.success(`Bench Boost charge bought · ${data.paid_remaining} extra`);
      const { data: bbd } = await api.get("/wc/bench-boost/status");
      setBB(bbd);
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    }
  };

  if (loading) return <div className="p-8 text-center text-sm opacity-60">Loading…</div>;
  if (!squad) return (
    <div className="p-8 text-center">
      <p className="text-sm opacity-60 mb-3">Team not found.</p>
      <Link to="/my-teams" className="text-cp-lime font-bold text-sm">← Back to My Teams</Link>
    </div>
  );

  return (
    <div className="max-w-[1100px] mx-auto p-3 md:p-5" data-testid="my-team-view">
      <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
        <Link to="/my-teams" className="text-xs inline-flex items-center gap-1 opacity-70 hover:opacity-100" data-testid="back-to-teams">
          <ArrowLeft size={12}/> My Teams
        </Link>
        <div className="flex items-center gap-2">
          <h1 className="text-base md:text-lg font-extrabold truncate max-w-[260px]">{squad.squad_name || (isMain ? "Main Squad" : "Mini-game entry")}</h1>
          <span className="cp-pill !text-[9px] !font-extrabold" style={{ background: isMain ? "rgba(163,230,53,0.2)" : "rgba(251,191,36,0.2)", color: isMain ? "#A3E635" : "#FBBF24" }}>
            {isMain ? "Main" : "Mini-game"}
          </span>
        </div>
        <div className="ml-auto flex gap-1 bg-white/5 rounded-md p-0.5 text-xs">
          <button onClick={() => setView("pitch")} className={`px-2 py-1 rounded inline-flex items-center gap-1 ${view === "pitch" ? "bg-cp-lime text-cp-forest font-bold" : ""}`} data-testid="view-pitch">
            <LayoutGrid size={12}/> Pitch
          </button>
          <button onClick={() => setView("list")} className={`px-2 py-1 rounded inline-flex items-center gap-1 ${view === "list" ? "bg-cp-lime text-cp-forest font-bold" : ""}`} data-testid="view-list">
            <List size={12}/> List
          </button>
        </div>
      </div>

      {/* Main-team round slider (WC stages) */}
      {isMain && rounds.length > 0 && (
        <RoundSlider rounds={rounds} activeIndex={activeIndex} onChange={setActiveIndex} />
      )}

      {/* Mini-game Bench Boost CTA */}
      {!isMain && (
        <div className="cp-surface p-3 mb-3 flex items-center gap-2 flex-wrap" data-testid="bench-boost-row">
          <ShieldCheck size={18} className="text-amber-400"/>
          <div className="flex-1 min-w-[200px]">
            <div className="text-sm font-extrabold">Bench Boost <span className="text-[10px] opacity-60">×1.5 multiplier on final points</span></div>
            <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
              {squad.bench_boost ? "Active on this entry." : (
                <>1 free + extra charges at 🪙 {bb?.price_coins || 500}. Free remaining: <b>{bb?.free_remaining ?? 0}</b> · Paid: <b>{bb?.paid_remaining ?? 0}</b></>
              )}
            </div>
          </div>
          {!squad.bench_boost && (
            <>
              <button onClick={activateBB} className="rounded px-3 py-1.5 text-xs font-extrabold bg-cp-lime text-cp-forest" data-testid="apply-bench-boost">
                Activate Bench Boost
              </button>
              <button onClick={buyBB} className="rounded px-3 py-1.5 text-xs font-extrabold inline-flex items-center gap-1 ring-1 ring-white/15" data-testid="buy-bench-boost">
                <Coins size={12}/> Buy charge
              </button>
            </>
          )}
        </div>
      )}

      {view === "pitch" ? (
        <PitchTeamView
          players={pitchPlayers}
          formation={squad.formation || "4-3-3"}
          captainId={squad.captain_id || squad.captain_player_id}
          viceId={squad.vice_captain_id || squad.vice_captain_player_id}
          benchBoost={!!squad.bench_boost}
          topStats={topStats}
          subtitle={isMain
            ? (rounds[activeIndex]?.round || "World Cup 2026")
            : (squad.game_title || "Mini-game")}
        />
      ) : (
        <div className="cp-surface p-3" data-testid="team-list-view">
          <table className="w-full text-sm">
            <thead className="text-[10px] uppercase tracking-widest" style={{ color: "var(--cp-text-muted)" }}>
              <tr className="border-b" style={{ borderColor: "var(--cp-border)" }}>
                <th className="text-left p-2">Player</th>
                <th className="text-center p-2">Pos</th>
                <th className="text-center p-2">Mins</th>
                <th className="text-right p-2">Pts</th>
              </tr>
            </thead>
            <tbody>
              {pitchPlayers
                .slice()
                .sort((a, b) => (b.points || 0) - (a.points || 0))
                .map((p) => (
                  <tr key={p.player_id} className="border-b hover:bg-white/[0.03]" style={{ borderColor: "var(--cp-border)" }}>
                    <td className="p-2 flex items-center gap-2">
                      {p.image_path && <img src={p.image_path} alt="" className="w-6 h-6 rounded-full object-cover"/>}
                      <span className="font-bold">{p.name}</span>
                      {p.captain && <Star size={11} className="text-cp-lime"/>}
                    </td>
                    <td className="p-2 text-center text-[10px] font-bold" style={{ color: "var(--cp-text-muted)" }}>{p.position}</td>
                    <td className="p-2 text-center tabular-nums">—</td>
                    <td className="p-2 text-right font-extrabold tabular-nums">{p.points}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Top-of-Round leaderboard — main team only, follows the active round */}
      {isMain && rounds.length > 0 && (
        <TopOfRound round={rounds[activeIndex]?.round} />
      )}

      <div className="mt-4"><AdSlot placement="match_list_inline"/></div>
    </div>
  );
}
