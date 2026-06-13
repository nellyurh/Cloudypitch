import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { useCurrency } from "../lib/currency";
import { flagUrl } from "../lib/flags";
import PlayerDetailSheet from "../components/PlayerDetailSheet";
import { CheckCircle2, X, Search, ChevronLeft, Trophy, Save, Zap, AlertTriangle, CreditCard, MinusCircle, ShoppingCart, Info, Repeat } from "lucide-react";

const POSITIONS = ["GK", "DEF", "MID", "FWD"];
const SQUAD_PROFILES = {
  "15": { total: 15, budget: 100, slots: { GK: 2, DEF: 5, MID: 5, FWD: 3 } },
  "20": { total: 20, budget: 120, slots: { GK: 3, DEF: 7, MID: 6, FWD: 4 } },
};
const POS_LABEL = { GK: "Goalkeepers", DEF: "Defenders", MID: "Midfielders", FWD: "Forwards" };
const POS_COLOR = { GK: "#FFC857", DEF: "#A3E635", MID: "#7DD3FC", FWD: "#FB7185" };

const fmt = (n) => `€${(n || 0).toFixed(1)}M`;

/** 3-letter uppercase code for a country, used for opponent labels. */
const COUNTRY_SHORT = {
  "South Korea": "KOR", "South Africa": "RSA", "United States": "USA", "USA": "USA",
  "Czech Republic": "CZE", "Cape Verde": "CPV", "Côte d'Ivoire": "CIV", "Cote d'Ivoire": "CIV",
  "Saudi Arabia": "KSA", "United Arab Emirates": "UAE", "New Zealand": "NZL",
  "Bosnia and Herzegovina": "BIH", "Central African Republic": "CAR",
  "Korea Republic": "KOR", "Korea DPR": "PRK", "Trinidad and Tobago": "TRI",
  "Northern Ireland": "NIR", "Republic of Ireland": "IRL", "Ivory Coast": "CIV",
  "Türkiye": "TUR", "Turkey": "TUR", "Equatorial Guinea": "EQG",
};
const shortCode = (name) => {
  if (!name) return "";
  if (COUNTRY_SHORT[name]) return COUNTRY_SHORT[name];
  // Default: first 3 letters uppercased, skipping spaces/apostrophes.
  return name.replace(/[^A-Za-zÀ-ÿ]/g, "").slice(0, 3).toUpperCase();
};

/** Parse "4-3-3" → { GK:1, DEF:4, MID:3, FWD:3 } */
function parseFormation(f) {
  const parts = (f || "4-3-3").split("-").map(n => parseInt(n, 10) || 0);
  const [DEF = 4, MID = 3, FWD = 3] = parts;
  return { GK: 1, DEF, MID, FWD };
}

/**
 * Circular player avatar — Sofascore fantasy style.
 * Sportmonks photo on top, country flag chip overlapping the bottom-left.
 * Falls back to a coloured jersey-position avatar when no photo URL.
 */
function PlayerPic({ player, size = 56, posColor = "#A3E635" }) {
  const initials = (player?.name || "?").split(" ").slice(-1)[0].slice(0, 1).toUpperCase();
  const photo = player?.photo_url;
  const flag = flagUrl(player?.country, 80);
  return (
    <span
      className="relative inline-block"
      style={{ width: size, height: size }}
    >
      <span
        className="absolute inset-0 rounded-full overflow-hidden flex items-center justify-center"
        style={{
          background: photo ? "#fff" : posColor,
          boxShadow: "0 2px 6px rgba(0,0,0,0.25), inset 0 0 0 2px rgba(255,255,255,0.9)",
        }}
      >
        {photo ? (
          <img
            src={photo}
            alt={player?.name || ""}
            loading="lazy"
            style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top center" }}
            onError={(e) => { e.currentTarget.style.display = "none"; }}
          />
        ) : (
          <span className="text-cp-forest font-extrabold" style={{ fontSize: size * 0.45 }}>{initials}</span>
        )}
      </span>
      {flag && (
        <img
          src={flag}
          alt={player?.country || ""}
          className="absolute"
          style={{
            left: -2, bottom: -2,
            width: Math.max(16, size * 0.36),
            height: Math.max(11, size * 0.26),
            objectFit: "cover",
            borderRadius: 3,
            border: "1.5px solid #fff",
            boxShadow: "0 1px 3px rgba(0,0,0,0.4)",
          }}
        />
      )}
    </span>
  );
}

/** A pitch slot — either populated or an empty "+ add" tile.
 *  Sizes scale on mobile so 7-wide defender rows (5-4-1 / 5-3-2) don't clip.
 *  `cardApplied` = { name, multiplier, position } when a legend card boost
 *  is attached to this player; renders a small badge at the top-left of the
 *  circle showing the multiplier (FUT-style "+xx%").
 */
function PitchSlot({ pos, picked, onPick, onTap, isCaptain, isVice, isBench, opponentCode, cardApplied }) {
  if (!picked) {
    return (
      <button
        onClick={() => onPick(pos)}
        className="flex flex-col items-center min-w-0 w-full max-w-[64px] sm:max-w-[92px] gap-1 hover:scale-105 transition"
        data-testid={`pitch-slot-empty-${pos}`}
      >
        <span
          className="rounded-full flex items-center justify-center text-cp-forest font-extrabold text-sm sm:text-xl shadow"
          style={{
            width: "clamp(36px, 11vw, 56px)",
            height: "clamp(36px, 11vw, 56px)",
            background: "rgba(255,255,255,0.85)",
            border: "2px dashed rgba(255,255,255,0.7)",
          }}
        >
          +
        </span>
        <span className="text-[8px] sm:text-[9px] font-bold px-1 rounded text-center" style={{ background: "rgba(0,0,0,0.55)", color: "#fff" }}>
          {pos}
        </span>
      </button>
    );
  }
  const lastName = (picked.name || "?").split(" ").slice(-1)[0];
  return (
    <div className={`flex flex-col items-center min-w-0 max-w-[64px] sm:max-w-[92px] w-full ${isBench ? "opacity-70" : ""}`} data-testid={`pitch-slot-${picked.id}`}>
      <button
        onClick={() => onTap(picked)}
        className="relative hover:scale-105 transition"
        title={isCaptain ? "Captain" : isVice ? "Vice-captain" : (isBench ? "On bench — tap to start" : "Tap for player info / remove")}
      >
        <ResponsivePlayerPic player={picked} posColor={POS_COLOR[pos]}/>
        {cardApplied && (
          <span
            className="absolute -top-1 -left-1 z-20 flex items-center gap-0.5 px-1 py-0.5 rounded text-[7px] sm:text-[9px] font-extrabold ring-2 ring-black/40 shadow-lg"
            style={{
              background: "linear-gradient(135deg, #FFD27A 0%, #F5A623 100%)",
              color: "#1B1B1B",
              minWidth: 18,
              justifyContent: "center",
            }}
            title={`${cardApplied.name} · +${Math.round((cardApplied.multiplier - 1) * 100)}%`}
            data-testid={`pitch-card-${picked.id}`}
          >
            ×{cardApplied.multiplier.toFixed(2)}
          </span>
        )}
        {isCaptain && (
          <span className="absolute -top-1 -right-1 bg-cp-lime text-cp-forest text-[8px] sm:text-[9px] font-extrabold w-4 h-4 sm:w-5 sm:h-5 rounded-full flex items-center justify-center ring-2 ring-black/40 z-10" data-testid={`captain-${picked.id}`}>C</span>
        )}
        {isVice && (
          <span className="absolute -top-1 -right-1 bg-white text-cp-forest text-[8px] sm:text-[9px] font-extrabold w-4 h-4 sm:w-5 sm:h-5 rounded-full flex items-center justify-center ring-2 ring-black/40 z-10" data-testid={`vice-${picked.id}`}>V</span>
        )}
        {isBench && (
          <span className="absolute -bottom-1 right-0 bg-amber-400 text-cp-forest text-[7px] sm:text-[8px] font-extrabold px-1 rounded ring-1 ring-black/40 z-10" data-testid={`bench-${picked.id}`}>B</span>
        )}
      </button>
      <div className="mt-1 w-full">
        <div className="text-[8px] sm:text-[10px] font-extrabold leading-tight px-0.5 py-0.5 rounded-t truncate text-center" style={{ background: "#3B5BDB", color: "#fff" }}>
          {lastName}
        </div>
        <div className="text-[7px] sm:text-[9px] font-bold leading-tight px-0.5 py-0.5 rounded-b truncate text-center" style={{ background: "#FFFFFF", color: "#1A1F26" }}>
          {opponentCode || fmt(picked.price)}
        </div>
      </div>
    </div>
  );
}

/** PlayerPic sized via clamp() so mobile 4-7-DEF rows don't clip. */
function ResponsivePlayerPic({ player, posColor }) {
  const initials = (player?.name || "?").split(" ").slice(-1)[0].slice(0, 1).toUpperCase();
  const photo = player?.photo_url;
  const flag = flagUrl(player?.country, 80);
  return (
    <span
      className="relative inline-block"
      style={{ width: "clamp(36px, 11vw, 56px)", height: "clamp(36px, 11vw, 56px)" }}
    >
      <span
        className="absolute inset-0 rounded-full overflow-hidden flex items-center justify-center"
        style={{
          background: photo ? "#fff" : posColor,
          boxShadow: "0 2px 6px rgba(0,0,0,0.25), inset 0 0 0 2px rgba(255,255,255,0.9)",
        }}
      >
        {photo ? (
          <img src={photo} alt={player?.name || ""} loading="lazy"
            style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top center" }}
            onError={(e) => { e.currentTarget.style.display = "none"; }}
          />
        ) : (
          <span className="text-cp-forest font-extrabold text-sm sm:text-xl">{initials}</span>
        )}
      </span>
      {flag && (
        <img src={flag} alt={player?.country || ""}
          className="absolute"
          style={{
            left: -2, bottom: -2,
            width: "clamp(14px, 4.2vw, 20px)",
            height: "clamp(10px, 3vw, 14px)",
            objectFit: "cover", borderRadius: 3,
            border: "1.5px solid #fff",
            boxShadow: "0 1px 3px rgba(0,0,0,0.4)",
          }}
        />
      )}
    </span>
  );
}

/** Build A Team — focused page, only the squad-build UI. */
export default function BuildTeam() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  // Main 15-man WC squad lives at /build-team (no game_id). 20-man mode ONLY
  // applies to mini-games with >2 teams (group / matchday / round). When a
  // game_id is present we trust gameRules; otherwise we hard-lock to 15.
  const gameId = searchParams.get("game_id");                  // mini-game scope
  const [gameRules, setGameRules] = useState(null); // {total, budget, max_per_country, slots, ...}
  const [gameTitle, setGameTitle] = useState(null);
  const mode = gameRules ? String(gameRules.total) : "15";
  const profile = gameRules
    ? { total: gameRules.total, budget: gameRules.budget, slots: gameRules.slots }
    : SQUAD_PROFILES["15"];
  const POS_LIMIT = profile.slots;
  const BUDGET = profile.budget;
  // Per-team cap (max players from one country). Main 15-man: 2 (anti-stacking).
  // Mini-games carry their own cap from `gameRules.max_per_country`.
  const MAX_PER_COUNTRY = gameRules?.max_per_country ?? 2;
  const [players, setPlayers] = useState([]);
  const [squad, setSquad] = useState([]);
  const [view, setView] = useState("pitch");
  const [pickerPos, setPickerPos] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [benchBoost, setBenchBoost] = useState(false);
  const [captainId, setCaptainId] = useState(null);
  const [viceId, setViceId] = useState(null);
  const [armbandStep, setArmbandStep] = useState(false);
  const [subStep, setSubStep] = useState(false); // substitutions mode — tap toggles bench
  const [formation, setFormation] = useState("4-3-3"); // starting XI shape
  const [benchIds, setBenchIds] = useState(new Set()); // player IDs on the bench
  const [originalIds, setOriginalIds] = useState(null); // snapshot of saved squad for transfer counting
  const [transfersInfo, setTransfersInfo] = useState({ remaining: 0, point_penalty_per_transfer: 4 });

  // FPL-style formations (excluding GK = 1). Min 3 DEF, 2 MID, 1 FWD.
  const FORMATIONS = mode === "20"
    ? ["4-4-2", "4-3-3", "3-5-2", "3-4-3", "5-3-2", "5-4-1", "4-5-1"] // 11 starters in 20-man too
    : ["4-3-3", "4-4-2", "3-5-2", "3-4-3", "5-3-2", "5-4-1", "4-5-1"];
  const benchTarget = profile.total - 11; // 4 for 15-man, 9 for 20-man
  const startersNeeded = parseFormation(formation); // { GK:1, DEF, MID, FWD }
  const cur = useCurrency();
  const [transferModal, setTransferModal] = useState(null); // { count, transfersInfo }
  const [transferBusy, setTransferBusy] = useState(false);
  // Map of country_name → opponent short code (R1). Pre-built once from /worldcup.
  const [opponentByCountry, setOpponentByCountry] = useState({});
  // Player detail bottom sheet — Sofascore-style. null = closed.
  const [detailPlayer, setDetailPlayer] = useState(null);

  // ===== Legend-card application state =====
  // ownedCards: user's cards w/ uses_remaining > 0. appliedCards: [{user_card_id, target_player_id}]
  // targetingCard: user_card_id currently being assigned to a player (null when not picking).
  const [ownedCards, setOwnedCards] = useState([]);
  const [appliedCards, setAppliedCards] = useState([]);
  const [targetingCard, setTargetingCard] = useState(null);

  useEffect(() => {
    (async () => {
      // First — if a game_id is in the URL, fetch its rules and use the
      // narrowed player pool. Otherwise use the full WC2026 pool.
      let rules = null;
      if (gameId) {
        try {
          const { data } = await api.get(`/fantasy/game-rules/${gameId}`);
          rules = data?.rules || null;
          if (rules) setGameRules(rules);
          if (data?.title) setGameTitle(data.title);
        } catch (_) {}
      }
      try {
        const qs = gameId ? `?game_id=${gameId}&limit=2000` : "?wc=true&limit=2000";
        const { data } = await api.get(`/fantasy/players${qs}`);
        setPlayers(data.players || []);
      } catch (_) {}
      try {
        const { data } = await api.get("/fantasy/transfers");
        setTransfersInfo(data);
      } catch (_) {}
      // Build R1 opponent lookup so pitch slots can show e.g. "MOR", "CRO".
      try {
        const { data } = await api.get("/worldcup");
        const map = {};
        const r1 = (data?.matches || []).filter(m => /matchday\s*1/i.test(m?.round || ""));
        for (const m of r1) {
          if (m.home_team_name && m.away_team_name) {
            map[m.home_team_name] = shortCode(m.away_team_name);
            map[m.away_team_name] = shortCode(m.home_team_name);
          }
        }
        setOpponentByCountry(map);
      } catch (_) {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId]);

  // Load existing squad — separate scope for mini-games vs main 15-man.
  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        // Mini-game → my entry for that game; Main → the WC2026 fantasy squad.
        const url = gameId ? `/wc/games/${gameId}` : "/fantasy/squad";
        const { data } = await api.get(url);
        const sq = gameId ? (data?.game?.my_entry) : (data?.squad);
        if (sq?.players) {
          // Main squad is hard-locked to 15-man — trim any legacy 20-man rows
          // so old over-stuffed squads still render cleanly.
          let picks = sq.players;
          if (!gameId && picks.length > 15) {
            picks = picks.slice(0, 15);
          }
          const hydrated = picks.map(sp => ({
            ...players.find(p => p.id === sp.player_id),
            ...sp,
            id: sp.player_id,
          })).filter(p => p.position);
          setSquad(hydrated);
          setOriginalIds(new Set(hydrated.map(p => p.id)));
          const cap = sq.players.find(p => p.is_captain);
          const vc = sq.players.find(p => p.is_vice);
          if (cap) setCaptainId(cap.player_id);
          if (vc) setViceId(vc.player_id);
          if (sq.bench_boost) setBenchBoost(true);
          if (sq.formation) setFormation(sq.formation);
          if (Array.isArray(sq.bench_ids)) setBenchIds(new Set(sq.bench_ids));
          // Restore per-player card targeting (main squad uses `applied_cards`;
          // mini-game entries use `cards_used` — normalise both into one shape).
          const restored = (sq.applied_cards || sq.cards_used || []).map(c => ({
            user_card_id: c.user_card_id, target_player_id: c.target_player_id,
          })).filter(c => c.user_card_id && c.target_player_id);
          setAppliedCards(restored);
        } else {
          // Reset state when switching scopes (main ↔ mini-game).
          setSquad([]);
          setOriginalIds(null);
          setCaptainId(null);
          setViceId(null);
          setBenchIds(new Set());
          setAppliedCards([]);
        }
      } catch (_) {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, players.length, gameId]);

  // Load owned legend cards (only those with uses_remaining > 0) — used by the
  // "Apply Boost Cards" panel and the pitch-circle multiplier badge.
  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        const { data } = await api.get("/cards/me");
        setOwnedCards((data.owned || []).filter(o => (o.uses_remaining ?? o.uses_left ?? 0) > 0));
      } catch (_) {}
    })();
  }, [user]);

  // Number of transfers since the saved snapshot (0 if first build)
  const transferCount = useMemo(() => {
    if (!originalIds) return 0;
    let n = 0;
    squad.forEach(p => { if (!originalIds.has(p.id)) n += 1; });
    return n;
  }, [squad, originalIds]);

  const counts = useMemo(() => {
    const c = { GK: 0, DEF: 0, MID: 0, FWD: 0 };
    squad.forEach(p => { if (c[p.position] != null) c[p.position] += 1; });
    return c;
  }, [squad]);

  // Lookup: player_id → applied card meta (used by PitchSlot for the badge).
  const cardsByPlayer = useMemo(() => {
    const m = {};
    for (const ac of appliedCards) {
      if (!ac.target_player_id) continue;
      const owned = ownedCards.find(o => o.id === ac.user_card_id);
      const card = owned?.card;
      if (!card) continue;
      m[ac.target_player_id] = {
        name: card.name,
        multiplier: Number(card.effect_value?.multiplier || 1),
        position: (card.position || "ANY").toUpperCase(),
      };
    }
    return m;
  }, [appliedCards, ownedCards]);

  // Card-application card cap — main squad uses the FPL-style 5-max-per-squad
  // shared with the rest of the app. Mini-games override via gameRules.
  const cardCap = 5;

  const toggleApplyCard = (uc) => {
    setAppliedCards(prev => {
      const exists = prev.find(c => c.user_card_id === uc.id);
      if (exists) return prev.filter(c => c.user_card_id !== uc.id);
      if (prev.length >= cardCap) return prev;
      // New card — open the player picker so the user attaches it to a slot.
      setTargetingCard(uc.id);
      return [...prev, { user_card_id: uc.id, target_player_id: null }];
    });
  };
  const setCardTarget = (user_card_id, target_player_id) => {
    setAppliedCards(prev => prev.map(c => c.user_card_id === user_card_id ? { ...c, target_player_id } : c));
    setTargetingCard(null);
  };
  // When a player is removed from the squad, drop any card targeting them.
  useEffect(() => {
    const ids = new Set(squad.map(p => p.id));
    setAppliedCards(prev => prev.filter(c => !c.target_player_id || ids.has(c.target_player_id)));
  }, [squad]);
  const totalSpent = useMemo(() => squad.reduce((s, p) => s + (p.price || 0), 0), [squad]);
  const remaining = BUDGET - totalSpent;
  const totalCount = squad.length;
  const isFull = totalCount === profile.total;

  // Auto-bench helper: given formation, mark cheapest extras in each position as benched.
  // Always keeps a valid formation (1 GK + DEF/MID/FWD from formation) starting.
  const autoBenchFor = (squadList, fmtParts) => {
    const need = fmtParts; // { GK:1, DEF, MID, FWD }
    const benched = new Set();
    POSITIONS.forEach(pos => {
      const inPos = squadList.filter(p => p.position === pos)
        .sort((a, b) => (b.price || 0) - (a.price || 0)); // expensive first → keep as starters
      const extra = inPos.slice(need[pos]); // everything past the formation quota goes to bench
      extra.forEach(p => benched.add(p.id));
    });
    return benched;
  };

  // When squad first becomes full OR formation changes, snap bench to a valid starting XI.
  // Only auto-reshuffle when current bench is empty/invalid; respect user manual picks otherwise.
  useEffect(() => {
    if (!isFull) return;
    // Count current starters by position
    const startersByPos = { GK: 0, DEF: 0, MID: 0, FWD: 0 };
    squad.forEach(p => { if (!benchIds.has(p.id)) startersByPos[p.position] += 1; });
    const matchesFormation = POSITIONS.every(pos => startersByPos[pos] === startersNeeded[pos]);
    if (matchesFormation && benchIds.size === benchTarget) return; // already valid
    const next = autoBenchFor(squad, startersNeeded);
    setBenchIds(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isFull, formation, mode]);

  // Country counts — used to enforce MAX_PER_COUNTRY across all picks.
  const countryCounts = useMemo(() => {
    const c = {};
    squad.forEach(p => { c[p.country] = (c[p.country] || 0) + 1; });
    return c;
  }, [squad]);

  const addPlayer = (p) => {
    if (squad.find(x => x.id === p.id)) return;
    if (counts[p.position] >= POS_LIMIT[p.position]) return;
    if (totalSpent + p.price > BUDGET) return;
    // Hard country cap — keeps users from stacking one nation on the main team
    // (anti-stacking) and follows the per-game caps for mini-games.
    if ((countryCounts[p.country] || 0) >= MAX_PER_COUNTRY) {
      alert(`Max ${MAX_PER_COUNTRY} player${MAX_PER_COUNTRY === 1 ? "" : "s"} from ${p.country} allowed${gameRules ? " in this game" : " in your main squad"}.`);
      return;
    }
    setSquad([...squad, p]);
    setPickerPos(null);
  };
  const removePlayer = (p) => {
    if (p.id === captainId) setCaptainId(null);
    if (p.id === viceId) setViceId(null);
    setSquad(squad.filter(x => x.id !== p.id));
  };

  // When armbandStep is on, tapping a player on the pitch sets C, then V.
  // When subStep is on, tapping toggles bench (enforcing formation min counts).
  // Otherwise tapping opens the Sofascore-style player detail sheet, which
  // has its own Remove + Replace buttons.
  const onPlayerTap = (p) => {
    if (armbandStep) {
      if (!captainId) {
        setCaptainId(p.id);
      } else if (!viceId && p.id !== captainId) {
        setViceId(p.id);
        setArmbandStep(false);
      } else if (p.id === captainId) {
        setCaptainId(null);
      } else if (p.id === viceId) {
        setViceId(null);
      }
      return;
    }
    if (subStep && isFull) {
      // Toggle bench, preserving formation. Same logic as legacy behaviour.
      setBenchIds(prev => {
        const next = new Set(prev);
        const startersByPos = { GK: 0, DEF: 0, MID: 0, FWD: 0 };
        squad.forEach(x => { if (!next.has(x.id)) startersByPos[x.position] += 1; });
        if (next.has(p.id)) {
          if (startersByPos[p.position] >= startersNeeded[p.position]) {
            alert(`${formation} formation already has ${startersNeeded[p.position]} starting ${p.position}. Bench another ${p.position} first.`);
            return prev;
          }
          next.delete(p.id);
        } else {
          if (startersByPos[p.position] <= startersNeeded[p.position] && (startersByPos[p.position] - 1) < startersNeeded[p.position]) {
            const benchedSamePos = squad.find(x => x.position === p.position && next.has(x.id));
            if (!benchedSamePos) {
              alert(`Cannot bench: formation ${formation} needs ${startersNeeded[p.position]} starting ${p.position}.`);
              return prev;
            }
            next.add(p.id);
            next.delete(benchedSamePos.id);
            return next;
          }
          if (next.size >= benchTarget) {
            alert(`Bench is full (${benchTarget}). Promote someone first.`);
            return prev;
          }
          next.add(p.id);
        }
        return next;
      });
      return;
    }
    // Default: open the Sofascore-style detail sheet.
    const full = players.find(x => x.id === p.id) || p;
    setDetailPlayer({ ...full, ...p });
  };

  // Replace flow — open the picker for the same position so the user can pick a new one.
  // The picker already runs the budget/limit checks.
  const onSheetReplace = (p) => {
    removePlayer(p);
    setPickerPos(p.position);
  };

  const saveSquad = async () => {
    if (isFull && !captainId) {
      alert("Pick a captain (2× points) before saving. Tap a player on the pitch.");
      setArmbandStep(true);
      return;
    }
    // Validate formation produces exactly 11 starters
    if (isFull) {
      const startersByPos = { GK: 0, DEF: 0, MID: 0, FWD: 0 };
      squad.forEach(p => { if (!benchIds.has(p.id)) startersByPos[p.position] += 1; });
      const wrong = POSITIONS.filter(pos => startersByPos[pos] !== startersNeeded[pos]);
      if (wrong.length) {
        alert(`Formation ${formation} needs ${startersNeeded.GK}-${startersNeeded.DEF}-${startersNeeded.MID}-${startersNeeded.FWD} starters. Fix ${wrong.join(", ")} before saving.`);
        return;
      }
    }
    // If editing a saved squad and we have transfers, show the modal
    if (originalIds && transferCount > 0) {
      setTransferModal({ count: transferCount });
      return;
    }
    await persistSquad();
  };

  const persistSquad = async () => {
    // Refuse to save if any applied card hasn't been targeted yet.
    if (appliedCards.some(c => !c.target_player_id)) {
      alert("One of your applied cards has no target player. Tap the card and pick a player.");
      return;
    }
    setSaving(true);
    try {
      const playerPicks = squad.map(p => ({
        player_id: p.id,
        position: p.position,
        price_paid: p.price || 0,
        is_captain: p.id === captainId,
        is_vice: p.id === viceId,
        on_bench: benchIds.has(p.id),
        is_starting: !benchIds.has(p.id),
      }));
      const appliedPayload = appliedCards
        .filter(c => c.user_card_id && c.target_player_id)
        .map(c => ({ user_card_id: c.user_card_id, target_player_id: c.target_player_id }));
      if (gameId) {
        // Mini-game entry — persist to the per-game collection so it doesn't
        // touch the user's main 15-man squad.
        await api.post(`/wc/games/${gameId}/enter`, {
          player_picks: playerPicks.map(p => ({
            player_id: p.player_id, position: p.position,
          })),
          captain_player_id: captainId,
          vice_captain_player_id: viceId,
          cards_used: appliedPayload,
        });
      } else {
        await api.post("/fantasy/squad", {
          competition_id: "fantasy-wc2026",
          squad_name: "My Squad",
          captain_id: captainId,
          vice_captain_id: viceId,
          formation,
          bench_ids: Array.from(benchIds),
          players: playerPicks,
          mode,
          bench_boost: benchBoost,
          applied_cards: appliedPayload,
        });
      }
      setSavedAt(new Date());
      setOriginalIds(new Set(squad.map(p => p.id))); // reset transfer baseline
    } catch (e) {
      alert(e?.response?.data?.detail || "Save failed");
    }
    setSaving(false);
  };

  const onTransferChoice = async (choice) => {
    if (!transferModal) return;
    setTransferBusy(true);
    try {
      if (choice === "buy") {
        await api.post("/fantasy/transfers/buy");
      }
      if (choice === "card" || choice === "buy") {
        for (let i = 0; i < transferModal.count; i += 1) {
          await api.post("/fantasy/transfers/spend", { pay_with: "card" });
        }
      } else if (choice === "points") {
        for (let i = 0; i < transferModal.count; i += 1) {
          await api.post("/fantasy/transfers/spend", { pay_with: "points" });
        }
      }
      // Refresh transfers state
      try {
        const { data } = await api.get("/fantasy/transfers");
        setTransfersInfo(data);
      } catch (_) {}
      setTransferModal(null);
      await persistSquad();
    } catch (e) {
      alert(`✗ ${e?.response?.data?.detail || e.message}`);
    }
    setTransferBusy(false);
  };

  return (
    <div className="max-w-[1400px] mx-auto p-3 md:p-5 pb-44 lg:pb-5" data-testid="build-team-page">
      {/* Scope banner — clarifies that mini-game squads are independent of the main 15-man. */}
      {gameId && (
        <div
          className="cp-surface mb-3 px-3 py-2 flex items-center gap-2 flex-wrap"
          style={{ borderLeft: "3px solid var(--cp-lime)" }}
          data-testid="mini-game-scope-banner"
        >
          <Trophy size={14} className="text-cp-lime"/>
          <span className="text-xs">
            <b>Mini-game team</b> — {gameTitle || "WC mini-game"}. This squad is <b>separate</b> from your main 15-man.
            Max <b>{MAX_PER_COUNTRY}</b> player{MAX_PER_COUNTRY === 1 ? "" : "s"} per country.
          </span>
          <Link to="/build-team" className="ml-auto text-[11px] font-bold underline" data-testid="back-to-main-squad">
            ← Back to main squad
          </Link>
        </div>
      )}
      <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
        <div className="flex items-center gap-2">
          <h1 className="text-xl md:text-2xl font-extrabold">{gameId ? (gameTitle || "Mini-game squad") : "Build a Team"}</h1>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider" style={{ background: "var(--cp-surface-2)", color: "var(--cp-text-muted)" }}>
            {profile.total}-man · €{profile.budget}M · max {MAX_PER_COUNTRY}/country
          </span>
        </div>
        <div className="flex items-center gap-2">
          {mode === "20" && (
            <button
              onClick={() => setBenchBoost(!benchBoost)}
              className={`px-2.5 py-1.5 rounded text-xs font-bold flex items-center gap-1 ${benchBoost ? "bg-cp-lime text-cp-forest" : ""}`}
              style={!benchBoost ? { background: "var(--cp-surface-2)" } : {}}
              data-testid="bench-boost-toggle"
              title="Bench Boost — bench players also score this game"
            >
              <Zap size={12}/> Bench Boost
            </button>
          )}
          <div className="flex items-center gap-1 cp-surface p-1 text-xs" role="tablist">
            <button onClick={() => setView("pitch")} className={`px-3 py-1.5 rounded ${view === "pitch" ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid="view-pitch">Pitch</button>
            <button onClick={() => setView("list")}  className={`px-3 py-1.5 rounded ${view === "list"  ? "bg-cp-lime text-cp-forest font-bold" : "hover:bg-white/5"}`} data-testid="view-list">List</button>
          </div>
        </div>
      </div>

      {/* Budget header */}
      <div className="cp-surface p-3 mb-3 grid grid-cols-3 md:grid-cols-4 gap-2 text-center" data-testid="budget-bar">
        <Stat label="Players" value={`${totalCount}/${profile.total}`} tone={isFull ? "good" : "warn"}/>
        <Stat label="Spent"   value={fmt(totalSpent)}/>
        <Stat label="Bank"    value={fmt(remaining)} tone={remaining < 0 ? "bad" : "good"}/>
        <button
          onClick={saveSquad}
          disabled={!isFull || saving}
          className="hidden md:flex items-center justify-center gap-2 rounded px-3 py-2 text-xs font-extrabold disabled:opacity-40"
          style={{ background: "var(--cp-lime)", color: "var(--cp-forest)" }}
          data-testid="save-squad"
        >
          <Save size={14}/> {saving ? "Saving…" : (savedAt ? "Saved ✓" : (mode === "20" ? "Save 20-man" : "Save squad"))}
        </button>
      </div>

      {/* Position progress dots */}
      <div className={`grid grid-cols-4 gap-2 mb-3`} data-testid="position-progress">
        {POSITIONS.map(pos => (
          <div key={pos} className="cp-surface p-2 text-center">
            <div className="text-[10px] uppercase font-bold opacity-60">{pos}</div>
            <div className="text-sm font-extrabold">{counts[pos]}/{POS_LIMIT[pos]}</div>
            <div className="flex gap-0.5 justify-center mt-1">
              {Array.from({ length: POS_LIMIT[pos] }).map((_, i) => (
                <span key={i} className="w-1.5 h-1.5 rounded-full" style={{ background: i < counts[pos] ? POS_COLOR[pos] : "var(--cp-border)" }}/>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Formation + bench-boost row — only meaningful once squad is full */}
      {isFull && (
        <div className="cp-surface p-2.5 mb-3 flex items-center gap-2 flex-wrap" data-testid="formation-bar">
          <span className="text-[10px] uppercase font-bold opacity-70 mr-1">Formation</span>
          {FORMATIONS.map(f => (
            <button
              key={f}
              onClick={() => setFormation(f)}
              className={`px-2 py-1 rounded text-[11px] font-bold ${formation === f ? "bg-cp-lime text-cp-forest" : "hover:bg-white/5"}`}
              style={formation !== f ? { background: "var(--cp-surface-2)" } : {}}
              data-testid={`formation-${f}`}
            >
              {f}
            </button>
          ))}
          <span className="ml-auto text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
            Bench: <b className="text-cp-lime">{benchIds.size}/{benchTarget}</b> · Tap a player to toggle bench
          </span>
        </div>
      )}

      {view === "pitch" ? (
        <PitchView counts={counts} squad={squad} onPick={setPickerPos} onTap={onPlayerTap} posLimit={POS_LIMIT} captainId={captainId} viceId={viceId} armbandStep={armbandStep} benchIds={benchIds} isFull={isFull} formation={formation} startersNeeded={startersNeeded} opponentByCountry={opponentByCountry} cardsByPlayer={cardsByPlayer}/>
      ) : (
        <ListView squad={squad} counts={counts} onPick={setPickerPos} onRemove={removePlayer} posLimit={POS_LIMIT} captainId={captainId} viceId={viceId} onSetCaptain={(p) => setCaptainId(p.id === captainId ? null : p.id)} onSetVice={(p) => setViceId(p.id === viceId ? null : p.id)} benchIds={benchIds} onToggleBench={(p) => onPlayerTap(p)} isFull={isFull}/>
      )}

      {/* === Apply Boost Cards === per-player legend-card targeting */}
      {ownedCards.length > 0 && (
        <BoostCardsPanel
          ownedCards={ownedCards}
          appliedCards={appliedCards}
          cardCap={cardCap}
          squad={squad}
          onToggle={toggleApplyCard}
          onRetarget={(uc_id) => setTargetingCard(uc_id)}
        />
      )}

      {/* Substitutions + Transfers — Sofascore-style bottom actions row.
          Always visible on every team page. */}
      <div className="cp-surface p-2 mt-3 grid grid-cols-2 gap-2" data-testid="team-actions-row">
        <button
          onClick={() => { setSubStep(!subStep); setArmbandStep(false); }}
          disabled={!isFull}
          className={`py-2.5 rounded font-extrabold text-sm flex items-center justify-center gap-2 disabled:opacity-40 ${subStep ? "bg-cp-lime text-cp-forest" : ""}`}
          style={!subStep ? { background: "var(--cp-surface-2)", color: "var(--cp-text)" } : {}}
          data-testid="substitutions-btn"
          title="Tap players to swap them between starting XI and bench"
        >
          <Repeat size={14}/> {subStep ? "Tap a player to bench/start" : "Substitutions"}
        </button>
        <button
          onClick={() => setTransferModal({ count: transferCount })}
          disabled={!originalIds || transferCount === 0}
          className="py-2.5 rounded font-extrabold text-sm flex items-center justify-center gap-2 disabled:opacity-40"
          style={{ background: "var(--cp-surface-2)", color: "var(--cp-text)" }}
          data-testid="transfers-btn"
          title={transferCount > 0 ? `Review ${transferCount} transfer${transferCount === 1 ? "" : "s"}` : "No pending transfers"}
        >
          <ShoppingCart size={14}/> Transfers {transferCount > 0 && <span className="cp-pill !text-[10px] bg-cp-lime text-cp-forest font-extrabold">{transferCount}</span>}
        </button>
      </div>

      {/* Armband picker bar — shows when squad is full but captain/vice unset */}
      {isFull && (!captainId || !viceId) && (
        <div className="cp-surface p-3 mt-3 flex items-center gap-3 flex-wrap" data-testid="armband-bar">
          <Trophy size={16} className="text-cp-lime"/>
          <div className="flex-1 min-w-[160px]">
            <div className="text-xs font-bold">Pick your captain & vice-captain</div>
            <div className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>
              Captain scores <b>2× points</b> · Vice auto-promotes if Captain doesn't play.
            </div>
          </div>
          <button
            onClick={() => setArmbandStep(!armbandStep)}
            className={`px-3 py-1.5 rounded text-xs font-extrabold ${armbandStep ? "bg-cp-lime text-cp-forest" : ""}`}
            style={!armbandStep ? { background: "var(--cp-surface-2)" } : {}}
            data-testid="armband-toggle"
          >
            {armbandStep ? "Picking…" : (captainId ? `Pick vice (C: ${squad.find(p => p.id === captainId)?.name.split(" ").slice(-1)[0]})` : "Tap to pick captain")}
          </button>
        </div>
      )}

      {/* Mobile sticky save bar — anchored ABOVE the bottom nav (z-40) and the
          mobile ad slot (bottom:56). z-50 ensures we never hide behind them. */}
      <button
        onClick={saveSquad}
        disabled={!isFull || saving}
        className="lg:hidden fixed left-3 right-3 flex items-center justify-center gap-2 rounded px-3 py-3 font-extrabold disabled:opacity-40 z-50"
        style={{ bottom: 128, background: "var(--cp-lime)", color: "var(--cp-forest)", boxShadow: "0 6px 24px rgba(0,0,0,0.4)" }}
        data-testid="save-squad-mobile"
      >
        <Save size={14}/> {saving ? "Saving…" : isFull ? (savedAt ? "Saved ✓" : "Save squad") : `Pick ${profile.total - totalCount} more`}
      </button>

      {/* Player picker modal */}
      {pickerPos && (
        <PlayerPicker
          position={pickerPos}
          allPlayers={players}
          alreadyPickedIds={new Set(squad.map(p => p.id))}
          counts={counts}
          countryCounts={countryCounts}
          maxPerCountry={MAX_PER_COUNTRY}
          remaining={remaining}
          onClose={() => setPickerPos(null)}
          onAdd={addPlayer}
          posLimit={POS_LIMIT}
        />
      )}

      {/* Transfer payment modal — only when editing a saved squad */}
      {transferModal && (
        <TransferModal
          count={transferModal.count}
          transfersInfo={transfersInfo}
          busy={transferBusy}
          cur={cur}
          onClose={() => !transferBusy && setTransferModal(null)}
          onChoice={onTransferChoice}
        />
      )}

      {/* Player detail bottom sheet — Sofascore-style */}
      {detailPlayer && (
        <PlayerDetailSheet
          player={detailPlayer}
          onClose={() => setDetailPlayer(null)}
          onRemove={removePlayer}
          onReplace={onSheetReplace}
          inSquad={true}
        />
      )}

      {/* Boost-card target picker — same pattern as WC mini-game */}
      {targetingCard && (
        <CardTargetPicker
          targetingCard={ownedCards.find(o => o.id === targetingCard)}
          squad={squad}
          appliedCards={appliedCards}
          onCancel={() => { setAppliedCards(ac => ac.filter(c => c.user_card_id !== targetingCard)); setTargetingCard(null); }}
          onPick={(pid) => setCardTarget(targetingCard, pid)}
        />
      )}
    </div>
  );
}

function Stat({ label, value, tone }) {
  const color = tone === "bad" ? "#FB7185" : tone === "good" ? "#A3E635" : "var(--cp-text)";
  return (
    <div>
      <div className="text-[10px] uppercase font-bold opacity-60">{label}</div>
      <div className="text-lg md:text-2xl font-extrabold tabular-nums" style={{ color }}>{value}</div>
    </div>
  );
}

function PitchView({ counts, squad, onPick, onTap, posLimit, captainId, viceId, armbandStep, benchIds, isFull, formation, startersNeeded, opponentByCountry = {}, cardsByPlayer = {} }) {
  // When the squad is NOT full → keep the legacy "build slots" layout so users can see empty + tiles.
  if (!isFull) {
    const slots = POSITIONS.flatMap(pos => {
      const picks = squad.filter(p => p.position === pos);
      const emptyN = posLimit[pos] - picks.length;
      return [
        ...picks.map(p => ({ pos, player: p })),
        ...Array.from({ length: emptyN }, () => ({ pos, player: null })),
      ];
    });
    const rowFor = (pos) => slots.filter(s => s.pos === pos);
    return (
      <div className="relative w-full rounded-lg overflow-hidden" style={pitchStyle} data-testid="build-team-pitch">
        <PitchLines/>
        {armbandStep && <ArmbandBanner captainId={captainId}/>}
        <div className="absolute inset-0 flex flex-col justify-around py-3">
          {POSITIONS.map(pos => (
            <div key={pos} className="flex items-start justify-around gap-1 px-1">
              {rowFor(pos).map((s, i) => (
                <PitchSlot key={`${pos}-${i}`} pos={pos} picked={s.player} onPick={onPick} onTap={onTap}
                  isCaptain={s.player?.id === captainId} isVice={s.player?.id === viceId}
                  isBench={s.player ? benchIds?.has(s.player.id) : false}
                  cardApplied={s.player ? cardsByPlayer[s.player.id] : null}
                  opponentCode={s.player ? opponentByCountry[s.player.country] : undefined}/>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // FULL squad → formation-driven Starting XI + bench row.
  const startersByPos = {
    GK: squad.filter(p => p.position === "GK" && !benchIds.has(p.id)),
    DEF: squad.filter(p => p.position === "DEF" && !benchIds.has(p.id)),
    MID: squad.filter(p => p.position === "MID" && !benchIds.has(p.id)),
    FWD: squad.filter(p => p.position === "FWD" && !benchIds.has(p.id)),
  };
  const benched = squad.filter(p => benchIds.has(p.id));

  return (
    <div className="space-y-2" data-testid="build-team-pitch-full">
      <div className="relative w-full rounded-lg overflow-hidden" style={pitchStyle}>
        <PitchLines/>
        {armbandStep && <ArmbandBanner captainId={captainId}/>}
        <div className="absolute inset-0 flex flex-col justify-around py-3" data-testid={`formation-row-${formation}`}>
          {POSITIONS.map(pos => (
            <div key={pos} className="flex items-start justify-around gap-1 px-1" data-testid={`pitch-row-${pos}`}>
              {startersByPos[pos].map((p) => (
                <PitchSlot key={p.id} pos={pos} picked={p} onPick={onPick} onTap={onTap}
                  isCaptain={p.id === captainId} isVice={p.id === viceId} isBench={false}
                  cardApplied={cardsByPlayer[p.id]}
                  opponentCode={opponentByCountry[p.country]}/>
              ))}
            </div>
          ))}
        </div>
      </div>
      {/* Bench row */}
      <div className="cp-surface p-2" data-testid="bench-row">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] uppercase font-bold opacity-70">Bench ({benched.length})</span>
          <span className="text-[10px]" style={{ color: "var(--cp-text-muted)" }}>Tap a bench player to promote · Tap pitch player to bench</span>
        </div>
        <div className="flex items-start gap-2 overflow-x-auto py-1" style={{ background: "rgba(255,255,255,0.04)", borderRadius: 8, padding: 8 }}>
          {benched.length === 0 ? (
            <div className="text-xs opacity-50 py-2 px-1">No bench players yet — pick a formation above.</div>
          ) : benched.map(p => (
            <PitchSlot key={p.id} pos={p.position} picked={p} onPick={onPick} onTap={onTap}
              isCaptain={p.id === captainId} isVice={p.id === viceId} isBench={true}
              cardApplied={cardsByPlayer[p.id]}
              opponentCode={opponentByCountry[p.country]}/>
          ))}
        </div>
      </div>
    </div>
  );
}

const pitchStyle = {
  aspectRatio: "10 / 14",
  background: "repeating-linear-gradient(180deg, #0E6B3A 0 7%, #0A5A31 7% 14%)",
  maxHeight: "70vh",
};

function PitchLines() {
  return (
    <>
      <div className="absolute top-1/2 left-0 right-0 h-px bg-white/50"/>
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 border border-white/50 rounded-full"/>
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[60%] h-[16%] border-x border-b border-white/50"/>
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[60%] h-[16%] border-x border-t border-white/50"/>
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[30%] h-[7%] border-x border-b border-white/50"/>
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[30%] h-[7%] border-x border-t border-white/50"/>
    </>
  );
}

function ArmbandBanner({ captainId }) {
  return (
    <div className="absolute top-2 left-2 right-2 z-10 cp-surface px-2 py-1.5 text-[10px] font-bold text-center" style={{ background: "rgba(0,0,0,0.7)", color: "#FBBF24" }}>
      Tap a player to set as {captainId ? "VICE-CAPTAIN" : "CAPTAIN"}
    </div>
  );
}

function ListView({ squad, counts, onPick, onRemove, posLimit, captainId, viceId, onSetCaptain, onSetVice, benchIds, onToggleBench, isFull }) {
  return (
    <div className="space-y-3" data-testid="build-team-list">
      {POSITIONS.map(pos => {
        const picks = squad.filter(p => p.position === pos);
        const empty = posLimit[pos] - picks.length;
        return (
          <div key={pos} className="cp-surface overflow-hidden">
            <div
              className="px-3 py-2 flex items-center justify-between"
              style={{ background: `${POS_COLOR[pos]}22`, borderBottom: "1px solid var(--cp-border)" }}
            >
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ background: POS_COLOR[pos] }}/>
                <span className="font-extrabold">{POS_LABEL[pos]}</span>
                <span className="text-xs opacity-60">{counts[pos]}/{posLimit[pos]}</span>
              </div>
              {empty > 0 && (
                <button onClick={() => onPick(pos)} className="text-xs font-bold px-2 py-1 rounded" style={{ background: POS_COLOR[pos], color: "var(--cp-forest)" }} data-testid={`list-add-${pos}`}>
                  + Add {pos}
                </button>
              )}
            </div>
            {picks.length === 0 ? (
              <div className="p-3 text-xs opacity-60 text-center">No {pos} picked yet. Tap "+ Add" to choose.</div>
            ) : (
              <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
                {picks.map(p => {
                  const isC = p.id === captainId;
                  const isV = p.id === viceId;
                  const isB = benchIds?.has(p.id);
                  return (
                    <li key={p.id} className={`flex items-center gap-3 p-2.5 ${isB ? "opacity-70" : ""}`} data-testid={`list-player-${p.id}`}>
                      <PlayerPic player={p} size={36} posColor={POS_COLOR[pos]}/>
                      <div className="flex-1 min-w-0">
                        <div className="font-bold truncate flex items-center gap-1">
                          {p.name}
                          {isC && <span className="bg-cp-lime text-cp-forest text-[9px] font-extrabold px-1 rounded">C</span>}
                          {isV && <span className="bg-white text-cp-forest text-[9px] font-extrabold px-1 rounded">V</span>}
                          {isB && <span className="bg-amber-400 text-cp-forest text-[9px] font-extrabold px-1 rounded">BENCH</span>}
                        </div>
                        <div className="text-[11px] opacity-60 truncate">{p.team_name}</div>
                      </div>
                      <div className="font-extrabold text-cp-lime tabular-nums">{fmt(p.price)}</div>
                      <div className="flex gap-1">
                        <button onClick={() => onSetCaptain(p)} title="Captain" className={`text-[10px] font-extrabold w-6 h-6 rounded ${isC ? "bg-cp-lime text-cp-forest" : "bg-white/10 hover:bg-white/20"}`} data-testid={`set-cap-${p.id}`}>C</button>
                        <button onClick={() => onSetVice(p)} title="Vice-captain" className={`text-[10px] font-extrabold w-6 h-6 rounded ${isV ? "bg-white text-cp-forest" : "bg-white/10 hover:bg-white/20"}`} data-testid={`set-vice-${p.id}`}>V</button>
                        {isFull && (
                          <button onClick={() => onToggleBench(p)} title={isB ? "Promote to starter" : "Send to bench"} className={`text-[10px] font-extrabold w-6 h-6 rounded ${isB ? "bg-amber-400 text-cp-forest" : "bg-white/10 hover:bg-white/20"}`} data-testid={`toggle-bench-${p.id}`}>B</button>
                        )}
                        <button onClick={() => onRemove(p)} className="cp-btn-ghost !p-1.5" data-testid={`list-remove-${p.id}`} aria-label="Remove">
                          <X size={12}/>
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Transfer payment modal — replaces window.prompt with a real UI */
function TransferModal({ count, transfersInfo, busy, cur, onClose, onChoice }) {
  const remaining = transfersInfo?.remaining || 0;
  const cardPack = transfersInfo?.card_uses || 5;
  const packCoins = transfersInfo?.card_price_coins || 300;
  const penaltyPer = transfersInfo?.point_penalty_per_transfer || 4;
  const totalPenalty = penaltyPer * count;
  const canUseCards = remaining >= count;
  const packPrice = `🪙 ${packCoins.toLocaleString()}`;
  return (
    <div className="fixed inset-0 z-[10001] flex items-end md:items-center justify-center p-0 md:p-4" data-testid="transfer-modal">
      <div className="absolute inset-0" onClick={onClose} style={{ background: "rgba(0,0,0,0.7)" }}/>
      <div className="relative w-full md:max-w-md rounded-t-2xl md:rounded-xl overflow-hidden animate-fade-in" style={{ background: "var(--cp-surface)", border: "1px solid var(--cp-border)" }}>
        <div className="px-4 py-3 flex items-center gap-2" style={{ borderBottom: "1px solid var(--cp-border)" }}>
          <AlertTriangle size={16} className="text-amber-400"/>
          <h2 className="font-extrabold">Confirm transfers</h2>
          <button onClick={onClose} disabled={busy} className="ml-auto cp-btn-ghost !p-2 disabled:opacity-40" data-testid="transfer-modal-close"><X size={14}/></button>
        </div>
        <div className="p-4 space-y-3">
          <div className="text-sm">
            You're transferring <b className="text-cp-lime">{count} player{count > 1 ? "s" : ""}</b>. Pick how to pay:
          </div>

          <button
            onClick={() => onChoice("card")}
            disabled={busy || !canUseCards}
            className="w-full text-left rounded-lg p-3 flex items-center gap-3 disabled:opacity-40 hover:bg-white/5 transition"
            style={{ border: "1px solid var(--cp-border)", background: canUseCards ? "rgba(163, 230, 53, 0.08)" : "var(--cp-surface-2)" }}
            data-testid="transfer-pay-card"
          >
            <CreditCard size={18} className="text-cp-lime"/>
            <div className="flex-1 min-w-0">
              <div className="font-extrabold text-sm">Pay with transfer cards</div>
              <div className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
                {canUseCards
                  ? `Use ${count} of ${remaining} remaining · no points penalty`
                  : `Not enough (${remaining} left, need ${count})`}
              </div>
            </div>
            <div className="text-xs font-bold opacity-70">{remaining} left</div>
          </button>

          <button
            onClick={() => onChoice("buy")}
            disabled={busy}
            className="w-full text-left rounded-lg p-3 flex items-center gap-3 disabled:opacity-40 hover:bg-white/5 transition"
            style={{ border: "1px solid var(--cp-border)", background: "rgba(125, 211, 252, 0.08)" }}
            data-testid="transfer-buy-pack"
          >
            <ShoppingCart size={18} className="text-sky-300"/>
            <div className="flex-1 min-w-0">
              <div className="font-extrabold text-sm">Buy transfer pack ({packPrice})</div>
              <div className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
                +{cardPack} transfers — uses wallet balance. Spends {count} now.
              </div>
            </div>
          </button>

          <button
            onClick={() => onChoice("points")}
            disabled={busy}
            className="w-full text-left rounded-lg p-3 flex items-center gap-3 disabled:opacity-40 hover:bg-white/5 transition"
            style={{ border: "1px solid var(--cp-border)", background: "rgba(251, 113, 133, 0.08)" }}
            data-testid="transfer-pay-points"
          >
            <MinusCircle size={18} className="text-rose-400"/>
            <div className="flex-1 min-w-0">
              <div className="font-extrabold text-sm">Take −{totalPenalty} points penalty</div>
              <div className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
                −{penaltyPer} pt per transfer applied next gameweek settlement.
              </div>
            </div>
          </button>

          {busy && (
            <div className="text-center text-xs opacity-70 pt-1" data-testid="transfer-busy">Processing transfers…</div>
          )}
        </div>
      </div>
    </div>
  );
}

function PlayerPicker({ position, allPlayers, alreadyPickedIds, counts, countryCounts = {}, maxPerCountry = 99, remaining, onClose, onAdd, posLimit }) {
  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("price");
  const limitReached = counts[position] >= posLimit[position];

  const teamOptions = useMemo(() => {
    const set = new Set(allPlayers.filter(p => p.position === position).map(p => p.team_name).filter(Boolean));
    return ["ALL", ...Array.from(set).sort()];
  }, [allPlayers, position]);

  // Pre-compute per-country slot counters so each row can render a "3/5" chip.
  const countriesInUse = Object.entries(countryCounts).filter(([_, n]) => n > 0);

  const list = useMemo(() => {
    const q = search.toLowerCase();
    const arr = allPlayers.filter(p =>
      p.position === position &&
      !alreadyPickedIds.has(p.id) &&
      (teamFilter === "ALL" || p.team_name === teamFilter) &&
      (!q || (p.name + " " + p.team_name).toLowerCase().includes(q))
    );
    if (sortBy === "price") arr.sort((a, b) => (b.price || 0) - (a.price || 0));
    else if (sortBy === "name") arr.sort((a, b) => a.name.localeCompare(b.name));
    return arr;
  }, [allPlayers, position, alreadyPickedIds, search, teamFilter, sortBy]);

  return (
    <div className="fixed inset-0 z-[10000] flex items-end md:items-center justify-center p-0 md:p-4" data-testid="player-picker">
      <div className="absolute inset-0" onClick={onClose} style={{ background: "rgba(0,0,0,0.6)" }}/>
      <div
        className="relative w-full md:max-w-2xl max-h-[88vh] flex flex-col rounded-t-2xl md:rounded-xl overflow-hidden animate-fade-in"
        style={{ background: "var(--cp-surface)", border: "1px solid var(--cp-border)" }}
      >
        <div className="flex items-center gap-2 p-3 shrink-0" style={{ borderBottom: "1px solid var(--cp-border)" }}>
          <button onClick={onClose} className="cp-btn-ghost !p-2 md:hidden" data-testid="picker-close-mobile"><ChevronLeft size={16}/></button>
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: POS_COLOR[position] }}/>
          <h2 className="font-extrabold">Pick a {POS_LABEL[position].slice(0, -1)}</h2>
          <span className="text-xs opacity-60 ml-auto">Bank {fmt(remaining)}</span>
          <button onClick={onClose} className="cp-btn-ghost !p-2 hidden md:inline-flex" data-testid="picker-close"><X size={16}/></button>
        </div>

        {/* Country tally strip — live "Portugal 3/5" chips for every country
            already on the squad. Helps users see who's still picking room. */}
        {countriesInUse.length > 0 && (
          <div className="px-3 pt-2 flex flex-wrap gap-1.5" data-testid="picker-country-tally">
            {countriesInUse.map(([c, n]) => {
              const atCap = n >= maxPerCountry;
              return (
                <span
                  key={c}
                  className="inline-flex items-center gap-1 text-[10px] font-extrabold px-1.5 py-0.5 rounded"
                  style={{
                    background: atCap ? "rgba(255, 107, 122, 0.18)" : "var(--cp-surface-2)",
                    color: atCap ? "#FF6B7A" : "var(--cp-text-muted)",
                    border: "1px solid " + (atCap ? "rgba(255, 107, 122, 0.4)" : "var(--cp-border)"),
                  }}
                  data-testid={`country-chip-${c.replace(/\s+/g, "-")}`}
                  title={atCap ? `${c} is at the ${maxPerCountry}-player cap` : ""}
                >
                  {flagUrl(c, 32) && (
                    <img src={flagUrl(c, 32)} alt="" style={{ width: 14, height: 10, objectFit: "cover", borderRadius: 2 }}/>
                  )}
                  <span className="truncate max-w-[80px]">{c}</span>
                  <span className="tabular-nums">{n}/{maxPerCountry}</span>
                </span>
              );
            })}
          </div>
        )}

        <div className="p-3 flex gap-2 shrink-0">
          <div className="relative flex-1">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 opacity-50"/>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search players or teams…"
              className="cp-input pl-7 w-full"
              data-testid="picker-search"
            />
          </div>
          <select value={teamFilter} onChange={e => setTeamFilter(e.target.value)} className="cp-input text-xs max-w-[140px]" data-testid="picker-team">
            {teamOptions.map(t => <option key={t} value={t}>{t === "ALL" ? "All teams" : t}</option>)}
          </select>
          <select value={sortBy} onChange={e => setSortBy(e.target.value)} className="cp-input text-xs max-w-[110px]" data-testid="picker-sort">
            <option value="price">€ High → Low</option>
            <option value="name">Name A–Z</option>
          </select>
        </div>
        <div className="flex-1 overflow-y-auto" data-testid="picker-list">
          {limitReached && (
            <div className="p-3 text-xs text-center bg-red-500/10 text-red-400">You already have {posLimit[position]} {position}s. Remove one first.</div>
          )}
          {list.length === 0 ? (
            <div className="p-6 text-center opacity-60 text-sm">No players match your filters.</div>
          ) : (
            <ul className="divide-y" style={{ borderColor: "var(--cp-border)" }}>
              {list.map(p => {
                const tooExpensive = p.price > remaining;
                const countryFull = (countryCounts[p.country] || 0) >= maxPerCountry;
                const disabled = limitReached || tooExpensive || countryFull;
                const tallyNow = countryCounts[p.country] || 0;
                return (
                  <li
                    key={p.id}
                    className={`flex items-center gap-3 p-2.5 transition ${disabled ? "opacity-40" : "hover:bg-white/3"}`}
                    data-testid={`picker-row-${p.id}`}
                  >
                    <PlayerPic player={p} size={36} posColor={POS_COLOR[position]}/>
                    <div className="flex-1 min-w-0">
                      <div className="font-bold truncate">{p.name}</div>
                      <div className="text-[11px] opacity-60 truncate flex items-center gap-1.5">
                        <span>{p.team_name}{p.shirt_number ? ` · #${p.shirt_number}` : ""}</span>
                        {/* Per-row country counter — appears once a player from
                            this country has been picked, so users see "3/5"
                            before they tap to add. */}
                        {tallyNow > 0 && (
                          <span className="font-extrabold tabular-nums px-1 rounded"
                            style={{
                              background: countryFull ? "rgba(255,107,122,0.18)" : "rgba(163,230,53,0.12)",
                              color: countryFull ? "#FF6B7A" : "#A3E635",
                            }}
                            data-testid={`row-country-tally-${p.id}`}
                          >
                            {tallyNow}/{maxPerCountry}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="font-extrabold text-cp-lime tabular-nums">{fmt(p.price)}</div>
                    <button
                      onClick={() => onAdd(p)}
                      disabled={disabled}
                      className="rounded px-2.5 py-1.5 text-xs font-extrabold disabled:cursor-not-allowed"
                      style={{ background: disabled ? "var(--cp-surface-2)" : "var(--cp-lime)", color: "var(--cp-forest)" }}
                      data-testid={`picker-add-${p.id}`}
                      title={countryFull ? `${p.country} is at the ${maxPerCountry}-player cap` : tooExpensive ? "Over budget" : limitReached ? "Position full" : "Add"}
                    >
                      <CheckCircle2 size={14}/>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}


/** Per-player legend-card application panel (main squad).
 *  Each owned card can boost ONE picked player. Position-locked cards (e.g.
 *  a striker card) cannot be attached to a non-striker — enforced client-side
 *  + by the backend. */
function BoostCardsPanel({ ownedCards, appliedCards, cardCap, squad, onToggle, onRetarget }) {
  return (
    <div className="cp-surface p-3 mt-3" data-testid="boost-cards-panel">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-extrabold inline-flex items-center gap-1.5">
          <Zap size={14} className="text-cp-lime"/> Apply Boost Cards
        </h3>
        <span className="text-[11px]" style={{ color: "var(--cp-text-muted)" }}>
          <span className="tabular-nums font-bold" style={{ color: "var(--cp-text)" }}>{appliedCards.length}</span>/{cardCap} applied
        </span>
      </div>
      <p className="text-[11px] mb-2" style={{ color: "var(--cp-text-muted)" }}>
        Each card boosts <b>ONE picked player</b>. Position-locked cards (e.g. a FWD card) can only target that position. Cards multiply that player&apos;s points at settlement.
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
        {ownedCards.map(uc => {
          const applied = appliedCards.find(c => c.user_card_id === uc.id);
          const sel = !!applied;
          const targeted = applied?.target_player_id ? squad.find(p => p.id === applied.target_player_id) : null;
          const lockPos = (uc.card?.position || "ANY").toUpperCase();
          const multiplier = Number(uc.card?.effect_value?.multiplier || 1);
          const pct = Math.round((multiplier - 1) * 100);
          const uses = uc.uses_remaining ?? uc.uses_left ?? 0;
          return (
            <div key={uc.id} className={`rounded text-xs ${sel ? "ring-1 ring-cp-lime bg-cp-lime/10" : ""}`} style={{ background: sel ? undefined : "var(--cp-surface-2)" }} data-testid={`bt-card-${uc.id}`}>
              <button
                onClick={() => onToggle(uc)}
                disabled={!sel && appliedCards.length >= cardCap}
                className="px-2 py-1.5 w-full text-left disabled:opacity-40"
                data-testid={`bt-card-toggle-${uc.id}`}
              >
                <div className="flex items-center gap-1.5">
                  <span className="font-extrabold truncate flex-1">{uc.card?.name}</span>
                  {lockPos !== "ANY" && (
                    <span className="cp-pill text-[8px] font-extrabold" style={{ background: POS_COLOR[lockPos] || "#666", color: "#0F1115" }} title={`${lockPos}-only card`}>{lockPos}</span>
                  )}
                </div>
                <div className="text-[10px] opacity-70 mt-0.5">+{pct}%{uses > 1 ? ` · ×${uses} owned` : ""}</div>
              </button>
              {sel && (
                <button
                  onClick={() => onRetarget(uc.id)}
                  className="w-full px-2 py-1 text-[10px] border-t inline-flex items-center justify-between gap-1"
                  style={{ borderColor: "var(--cp-border)", color: targeted ? "#A3E635" : "#FBBF24" }}
                  data-testid={`bt-card-target-${uc.id}`}
                >
                  <span className="truncate">{targeted ? `→ ${targeted.name}` : "→ Pick target player"}</span>
                  <span>change</span>
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Full-screen target picker for assigning a card to a picked player. */
function CardTargetPicker({ targetingCard, squad, appliedCards, onCancel, onPick }) {
  if (!targetingCard) return null;
  const lockPos = (targetingCard.card?.position || "ANY").toUpperCase();
  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-3" style={{ background: "rgba(0,0,0,0.85)" }} data-testid="bt-target-picker">
      <div className="cp-surface w-full max-w-md max-h-[80vh] overflow-hidden flex flex-col">
        <div className="px-4 py-3 flex items-center justify-between border-b" style={{ borderColor: "var(--cp-border)" }}>
          <div>
            <div className="text-[10px] uppercase tracking-widest text-cp-lime">
              Boost target {lockPos !== "ANY" ? `\u00b7 ${lockPos} only` : ""}
            </div>
            <div className="text-sm font-extrabold">{targetingCard.card?.name}</div>
          </div>
          <button onClick={onCancel} className="cp-btn-ghost !p-2" data-testid="bt-target-cancel">\u2715</button>
        </div>
        <div className="overflow-y-auto p-2">
          {squad.length === 0 && (
            <div className="p-4 text-xs text-center" style={{ color: "var(--cp-text-muted)" }}>Pick players first, then apply cards to them.</div>
          )}
          {squad.map(p => {
            const usedByOther = appliedCards.find(c => c.target_player_id === p.id && c.user_card_id !== targetingCard.id);
            const posMismatch = lockPos !== "ANY" && (p.position || "").toUpperCase() !== lockPos;
            const disabled = !!usedByOther || posMismatch;
            const reasonLabel = posMismatch ? `${lockPos} only` : (usedByOther ? "boosted" : null);
            return (
              <button
                key={p.id}
                onClick={() => !disabled && onPick(p.id)}
                disabled={disabled}
                className="w-full px-2 py-1.5 text-left text-sm rounded hover:bg-white/5 disabled:opacity-30 flex items-center gap-2"
                data-testid={`bt-target-pick-${p.id}`}
              >
                <span className="cp-pill text-[9px] font-bold" style={{ background: "var(--cp-surface-2)", color: POS_COLOR[p.position] }}>{p.position}</span>
                <span className="flex-1 truncate">{p.name}</span>
                {reasonLabel && <span className="text-[10px]" style={{ color: posMismatch ? "#FBBF24" : "var(--cp-text-muted)" }}>{reasonLabel}</span>}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
