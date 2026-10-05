export const SMALL_N = 30;

export function lastIndex(values, keep = (v) => v != null) {
  for (let i = values.length - 1; i >= 0; i--) if (keep(values[i], i)) return i;
  return -1;
}

export function peakIndex(values) {
  let k = -1;
  values.forEach((v, i) => {
    if (v != null && (k < 0 || v > values[k])) k = i;
  });
  return k;
}

export function deformitySeries(d) {
  const top = d.weeks.map((_, j) => Math.max(0, ...d.types.map((type) => d.counts[type][j])));
  const latest = lastIndex(d.n_rotten, (n) => n > 0);
  return {
    weeks: d.weeks,
    types: d.types,
    n: d.n_rotten,
    shares: Object.fromEntries(d.types.map((type) => [type, d.counts[type].map((c, j) => (d.n_rotten[j] ? c / d.n_rotten[j] : null))])),
    counts: d.counts,
    dominant: Object.fromEntries(d.types.map((type) => [type, d.counts[type].map((c, j) => d.n_rotten[j] > 0 && c === top[j])])),
    empty: d.n_rotten.flatMap((n, j) => (n ? [] : [j])),
    latest: latest < 0 ? null : { index: latest, type: d.dominant[latest], share: d.share[latest], tie: d.tie[latest], n: d.n_rotten[latest] },
  };
}

export function forecastSeries(s, labels, target) {
  const n = labels.length;
  const last = lastIndex(s.history);
  const ok = s.status === "ok" && last >= 0;
  const tail = (a, b) => Array.from({ length: n + 1 }, (_, i) => (ok && i === last ? a : ok && i === n ? b : null));
  return {
    sector: s.sector,
    labels: [...labels, target],
    history: [...s.history, null],
    historyN: [...(s.history_n || []), null],
    forecast: tail(s.history[last], s.rotten_pred),
    hi: tail(s.history[last], s.rotten_hi),
    lo: tail(s.history[last], s.rotten_lo),
    last,
    ok,
    observed: s.history.filter((v) => v != null).length,
    pred: s.rotten_pred,
    low: s.rotten_lo,
    high: s.rotten_hi,
    p: s.p_more_rotten,
    slope: s.slope,
    reliable: s.reliable,
    reasons: s.reasons,
    fruits: s.fruits,
    nPeriods: s.n_periods,
    mae: s.bt_mae,
    naive: s.bt_naive_mae,
  };
}

export function fruitSeries(f) {
  const values = f.items.map((i) => i.n);
  const max = Math.max(0, ...values);
  const winners = values.map((v) => max > 0 && v === max);
  return {
    labels: f.items.map((i) => i.fruit),
    values,
    shares: f.items.map((i) => i.share),
    winners,
    tie: winners.filter(Boolean).length > 1,
    total: values.reduce((a, b) => a + b, 0),
  };
}

export function growthSeries(g, kind) {
  const count = g[kind].count_growth;
  const last = lastIndex(count);
  return {
    labels: g.labels,
    count,
    prop: g[kind].prop_growth,
    n: g.good.count.map((v, i) => v + g.rotten.count[i]),
    na: count.flatMap((v, i) => (v == null ? [i] : [])),
    sign: count.map((v) => (v == null ? 0 : Math.sign(v))),
    last: last < 0 ? null : { index: last, value: count[last] },
  };
}

export function growthRange(g) {
  const all = ["good", "rotten"].flatMap((k) => [...g[k].count_growth, ...g[k].prop_growth]).filter((v) => v != null && Number.isFinite(v));
  const m = Math.max(0.05, ...all.map(Math.abs));
  return { min: -m, max: m };
}

export function recurringSeries(r, which) {
  const t = r[which];
  return {
    buckets: t.buckets,
    good: t.good,
    rotten: t.rotten,
    goodN: t.good_n,
    rottenN: t.rotten_n,
    peakGood: peakIndex(t.good),
    peakRotten: peakIndex(t.rotten),
    maxN: t.max_n,
    excluded: t.excluded,
    n: t.n,
  };
}

export function gaussianSeries(s) {
  const base = { sector: s.sector, n: s.n, mean: s.mean, std: s.std, flagged: s.flagged, reasons: s.reasons, shapiroP: s.shapiro_p, shapiroW: s.shapiro_w, outside: s.mass_outside_01 };
  if (!s.hist) return { ...base, ok: false };
  const { edges, density } = s.hist;
  const ends = [s.qq.theoretical[0], s.qq.theoretical[s.qq.theoretical.length - 1]];
  return {
    ...base,
    ok: true,
    bins: density.map((y, i) => ({ x: (edges[i] + edges[i + 1]) / 2, y, width: edges[i + 1] - edges[i], count: Math.round(y * (edges[i + 1] - edges[i]) * s.n) })),
    curve: s.pdf.x.map((x, i) => ({ x, y: s.pdf.y[i] })),
    sigma1: [s.mean - s.std, s.mean + s.std],
    sigma2: [s.mean - 2 * s.std, s.mean + 2 * s.std],
    range: [Math.min(edges[0], s.pdf.x[0]), Math.max(edges[edges.length - 1], s.pdf.x[s.pdf.x.length - 1])],
    qq: s.qq.theoretical.map((x, i) => ({ x, y: s.qq.observed[i] })),
    qqLine: ends.map((x) => ({ x, y: s.qq.intercept + s.qq.slope * x })),
  };
}

export function overviewSeries(o) {
  const totals = o.good.map((g, i) => g + o.rotten[i]);
  const sectors = [...o.sectors].sort((a, b) => b.rotten_rate - a.rotten_rate);
  return {
    labels: o.labels,
    good: o.good,
    rotten: o.rotten,
    totals,
    rate: totals.map((n, i) => (n ? o.rotten[i] / n : null)),
    total: o.n,
    rottenRate: o.rotten_rate,
    sectors: sectors.map((s) => s.sector),
    sectorRates: sectors.map((s) => s.rotten_rate),
    sectorN: sectors.map((s) => s.n),
  };
}
