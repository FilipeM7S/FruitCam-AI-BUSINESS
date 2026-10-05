import { t } from "./strings.js";

const intl = new Intl.NumberFormat("pt-BR");

export function num(x) {
  return x == null ? "—" : intl.format(x);
}

export function pct(x, digits = 1) {
  return x == null ? t.cards.growth.undefined : new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: digits }).format(x);
}

export function confidence(x) {
  return x >= 0.9995 ? "> 99,9%" : pct(x);
}

export function signedPct(x) {
  return x == null ? t.cards.growth.undefined : `${x > 0 ? "+" : ""}${pct(x)}`;
}

export function prob(p) {
  if (p == null) return "—";
  if (p > 0.99) return "> 99%";
  if (p < 0.01) return "< 1%";
  return pct(p, 0);
}

export function dec(x, digits = 3) {
  return x == null ? "—" : x.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function periodLabel(label, period) {
  if (period === "month") {
    const [y, m] = label.split("-");
    return `${t.months[Number(m) - 1]}/${y.slice(2)}`;
  }
  const [y, m, d] = label.split("-");
  return `${d}/${m}/${y.slice(2)}`;
}

export function fruitName(f) {
  return t.fruits[f] || f;
}

export function deformityName(d) {
  return t.deformities[d] || d;
}
