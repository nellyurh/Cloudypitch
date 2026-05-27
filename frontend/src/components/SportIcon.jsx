import React from "react";

// FontAwesome icon class per sport. Falls back to a generic icon if not in FA free.
const ICONS = {
  football: "fa-solid fa-futbol",
  basketball: "fa-solid fa-basketball",
  tennis: "fa-solid fa-baseball",          // FA free has no tennis ball; use baseball shape
  baseball: "fa-solid fa-baseball-bat-ball",
  hockey: "fa-solid fa-hockey-puck",
  cricket: "fa-solid fa-baseball-bat-ball",
  rugby: "fa-solid fa-football",
  nba: "fa-solid fa-basketball",
  volleyball: "fa-solid fa-volleyball",
  handball: "fa-solid fa-hand-fist",
  mma: "fa-solid fa-hand-fist",
  f1: "fa-solid fa-flag-checkered",
  afl: "fa-solid fa-football",
  golf: "fa-solid fa-golf-ball-tee",
};

export const SportIcon = ({ slug, className = "" }) => {
  const cls = ICONS[slug] || "fa-solid fa-trophy";
  return <i className={`${cls} ${className}`.trim()} aria-hidden />;
};

export default SportIcon;
