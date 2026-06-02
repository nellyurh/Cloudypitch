import { useEffect, useState } from "react";
import api from "./api";

let _cur = { code: "USD", symbol: "$", rate: 1.0, country: "WORLD" };
const _subs = new Set();
function _emit() { _subs.forEach(fn => fn(_cur)); }

export async function refreshCurrency() {
  try {
    const { data } = await api.get("/currency");
    _cur = data;
    _emit();
  } catch (_) {}
}

/** React hook — returns { code, symbol, rate, country, format(usd_amount), formatCents(cents) } */
export function useCurrency() {
  const [c, setC] = useState(_cur);
  useEffect(() => {
    _subs.add(setC);
    if (_cur.country === "WORLD") refreshCurrency();
    return () => _subs.delete(setC);
  }, []);
  const format = (usd) => {
    const v = (usd || 0) * c.rate;
    return `${c.symbol}${v.toLocaleString(undefined, { maximumFractionDigits: c.code === "NGN" ? 0 : 2, minimumFractionDigits: c.code === "NGN" ? 0 : 2 })}`;
  };
  const formatCents = (cents) => format((cents || 0) / 100);
  return { ...c, format, formatCents };
}
