import {
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  ScatterController,
  Tooltip,
} from "chart.js";
import { fill, t } from "./strings.js";
import { dec, deformityName, fruitName, num, pct, periodLabel, prob, signedPct } from "./format.js";
import { lastIndex } from "./series.js";

export const C = {
  good: "#2fbf8f",
  rotten: "#E8742A",
  poor: "#E6B13C",
  review: "#CC79A7",
  up: "#56B4E9",
  down: "#E69F00",
  hist: "#56B4E9",
  deformity: ["#E8742A", "#E6B13C", "#CC79A7", "#56B4E9", "#9ad0f0"],
  ink: "#e4eee8",
  muted: "#9fb3a7",
  grid: "rgba(207, 224, 214, 0.12)",
};

export function alpha(hex, a) {
  const v = parseInt(hex.slice(1), 16);
  return `rgba(${v >> 16}, ${(v >> 8) & 255}, ${v & 255}, ${a})`;
}

export const reduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const narrow = () => typeof window !== "undefined" && window.innerWidth < 520;

let batch = 0;
let batchTimer = 0;
export function stagger() {
  const d = batch++ * 110;
  clearTimeout(batchTimer);
  batchTimer = setTimeout(() => (batch = 0), 450);
  return d;
}

const marks = {
  id: "marks",
  beforeDatasetsDraw(chart, _, opts) {
    const { ctx, chartArea: a, scales } = chart;
    if (!a || !opts) return;
    ctx.save();
    for (const b of opts.bands || []) {
      const p0 = scales.x.getPixelForValue(b.from);
      const p1 = scales.x.getPixelForValue(b.to);
      const l = Math.max(a.left, Math.min(p0, p1));
      const r = Math.min(a.right, Math.max(p0, p1));
      ctx.fillStyle = b.color;
      if (r > l) ctx.fillRect(l, a.top, r - l, a.bottom - a.top);
    }
    for (const line of opts.lines || []) {
      const vertical = line.axis === "x";
      const p = scales[vertical ? "x" : "y"].getPixelForValue(line.at);
      if (vertical ? p < a.left || p > a.right : p < a.top || p > a.bottom) continue;
      ctx.beginPath();
      ctx.setLineDash(line.dash || []);
      ctx.lineWidth = line.width || 1.5;
      ctx.strokeStyle = line.color;
      ctx.moveTo(vertical ? p : a.left, vertical ? a.top : p);
      ctx.lineTo(vertical ? p : a.right, vertical ? a.bottom : p);
      ctx.stroke();
    }
    ctx.restore();
  },
};

const dim = {
  id: "dim",
  beforeDatasetDraw(chart, args) {
    const d = chart.$dim;
    if (!d || d.index == null || args.index === d.index || !d.amount) return;
    chart.ctx.save();
    chart.ctx.globalAlpha = 1 - 0.75 * d.amount;
    args.meta.$dimmed = true;
  },
  afterDatasetDraw(chart, args) {
    if (!args.meta.$dimmed) return;
    chart.ctx.restore();
    args.meta.$dimmed = false;
  },
};

Chart.register(BarController, BarElement, CategoryScale, Filler, Legend, LinearScale, LineController, LineElement, PointElement, ScatterController, Tooltip, marks, dim);
Chart.defaults.font.family = getComputedStyle(document.documentElement).getPropertyValue("--font").trim() || "system-ui, sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.color = C.muted;
Chart.defaults.borderColor = C.grid;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.plugins.legend.labels.boxWidth = 12;
Chart.defaults.plugins.legend.labels.boxHeight = 12;
Chart.defaults.plugins.legend.labels.useBorderRadius = true;
Chart.defaults.plugins.legend.labels.borderRadius = 3;
Chart.defaults.plugins.tooltip.backgroundColor = "#0b1511";
Chart.defaults.plugins.tooltip.borderColor = "rgba(159, 211, 177, 0.35)";
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.titleColor = "#e4eee8";
Chart.defaults.plugins.tooltip.bodyColor = "#cfe0d6";
Chart.defaults.plugins.tooltip.footerColor = "#9fb3a7";
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.cornerRadius = 8;

export { Chart };

const patterns = {};
function hatch(color) {
  if (patterns[color]) return patterns[color];
  const c = document.createElement("canvas");
  c.width = c.height = 8;
  const x = c.getContext("2d");
  x.strokeStyle = color;
  x.lineWidth = 1.4;
  x.beginPath();
  for (const o of [-8, 0, 8]) {
    x.moveTo(o, 8);
    x.lineTo(o + 8, 0);
  }
  x.stroke();
  return (patterns[color] = x.createPattern(c, "repeat"));
}

function fade(color, top = 0.3, bottom = 0.02) {
  return ({ chart }) => {
    const a = chart.chartArea;
    if (!a) return alpha(color, top);
    const g = chart.ctx.createLinearGradient(0, a.top, 0, a.bottom);
    g.addColorStop(0, alpha(color, top));
    g.addColorStop(1, alpha(color, bottom));
    return g;
  };
}

export function elRect(chart, d, i) {
  const el = chart.getDatasetMeta(d)?.data?.[i];
  if (!el) return null;
  const p = el.getProps(["x", "y", "base", "width", "height", "horizontal"], true);
  if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) return null;
  if (p.base == null || !Number.isFinite(p.base)) return { left: p.x - 7, right: p.x + 7, top: p.y - 7, bottom: p.y + 7 };
  if (p.horizontal) return { left: Math.min(p.x, p.base), right: Math.max(p.x, p.base), top: p.y - p.height / 2, bottom: p.y + p.height / 2 };
  return { left: p.x - p.width / 2, right: p.x + p.width / 2, top: Math.min(p.y, p.base), bottom: Math.max(p.y, p.base) };
}

const pctTicks = (digits = 0) => ({ callback: (v) => pct(v, digits) });
const xCat = () => ({ grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, autoSkipPadding: 14, maxTicksLimit: narrow() ? 4 : 8 } });
const zeroGrid = (value) => ({ color: (c) => (c.tick?.value === value ? C.muted : C.grid), lineWidth: (c) => (c.tick?.value === value ? 1.5 : 1) });
const legendFull = (items) => ({
  labels: { generateLabels: (chart) => items.map(([text, color], i) => ({ text, fillStyle: color, strokeStyle: color, lineWidth: 0, datasetIndex: i, hidden: !chart.isDatasetVisible(i) })) },
});
const arrow = (v) => (v > 0 ? "↑" : v < 0 ? "↓" : "→");
const trend = (v) => (v > 0 ? "↗" : v < 0 ? "↘" : "→");

function na(chart, i, y) {
  const x = chart.scales.x.getPixelForValue(i);
  return { key: `na${i}`, kind: "na", x, y: y ?? chart.chartArea.bottom - 4, text: t.charts.na, place: "above" };
}

export function deformitySpec(s) {
  const labels = s.weeks.map((w) => periodLabel(w, "week"));
  const L = s.latest;
  const typeIndex = L ? s.types.indexOf(L.type) : -1;
  const firstFull = s.n.findIndex((n) => n > 0);
  return {
    config: {
      type: "bar",
      data: {
        labels,
        datasets: s.types.map((type, i) => {
          const color = C.deformity[i % C.deformity.length];
          return {
            label: deformityName(type),
            data: s.shares[type],
            backgroundColor: s.dominant[type].map((on) => (on ? color : alpha(color, 0.28))),
            hoverBackgroundColor: color,
            borderWidth: 0,
            stack: "s",
            barPercentage: 0.94,
            categoryPercentage: 0.96,
          };
        }),
      },
      options: {
        scales: { x: { stacked: true, ...xCat() }, y: { stacked: true, min: 0, max: 1, ticks: pctTicks() } },
        plugins: {
          legend: legendFull(s.types.map((type, i) => [deformityName(type), C.deformity[i % C.deformity.length]])),
          tooltip: {
            callbacks: {
              title: (items) => fill(t.charts.weekOf, { week: labels[items[0].dataIndex] }),
              label: (c) => `${c.dataset.label}: ${pct(c.raw)} (${num(s.counts[s.types[c.datasetIndex]][c.dataIndex])})`,
              footer: (items) => fill(t.charts.nRotten, { n: num(s.n[items[0].dataIndex]) }),
            },
          },
        },
      },
    },
    finding: L ? fill(t.cards.deformity.finding, { week: labels[L.index], type: deformityName(L.type), share: pct(L.share) }) : t.cards.deformity.none,
    overlays: (chart) => {
      const out = s.empty.map((j) => na(chart, j));
      const r = L && elRect(chart, typeIndex, L.index);
      if (r) out.push({ key: "latest", kind: "callout", tone: "ink", x: r.left - 6, y: (r.top + r.bottom) / 2, place: "left", text: `${deformityName(L.type)} ${pct(L.share, 0)}`, sub: L.tie ? t.cards.deformity.tie : labels[L.index] });
      return out;
    },
    steps: [
      { target: { area: "legend" }, text: t.cards.deformity.steps[0] },
      { target: { el: [0, firstFull] }, text: t.cards.deformity.steps[1] },
      { target: typeIndex >= 0 ? { el: [typeIndex, L.index] } : { area: "chart" }, text: t.cards.deformity.steps[2] },
      { target: { selector: ".n-badge" }, text: t.cards.deformity.steps[3] },
    ],
  };
}

export const FORECAST_WINDOW = 12;

export function forecastSpec(s, period) {
  const total = s.labels.length - 1;
  const start = Math.max(0, Math.min(total - FORECAST_WINDOW, s.last < 0 ? total : s.last));
  const cut = (a) => a.slice(start);
  const labels = cut(s.labels).map((l) => periodLabel(String(l).split("/")[0], period));
  const n = labels.length - 1;
  const last = s.last - start;
  const band = s.reliable ? alpha(C.rotten, 0.28) : hatch(alpha(C.rotten, 0.6));
  return {
    config: {
      type: "line",
      data: {
        labels,
        datasets: [
          { label: t.charts.history, data: cut(s.history), borderColor: C.rotten, backgroundColor: C.rotten, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.25, spanGaps: false },
          { label: t.charts.bandHigh, data: cut(s.hi), borderColor: alpha(C.rotten, 0.55), borderWidth: 1, borderDash: [3, 3], pointRadius: (c) => (c.dataIndex === n ? 9 : 0), pointStyle: "line", pointBorderWidth: 2.5, pointBorderColor: C.rotten, fill: "+1", backgroundColor: band, spanGaps: true },
          { label: t.charts.bandLow, data: cut(s.lo), borderColor: alpha(C.rotten, 0.55), borderWidth: 1, borderDash: [3, 3], pointRadius: (c) => (c.dataIndex === n ? 9 : 0), pointStyle: "line", pointBorderWidth: 2.5, pointBorderColor: C.rotten, fill: false, spanGaps: true },
          { label: t.charts.forecast, data: cut(s.forecast), borderColor: C.ink, backgroundColor: C.ink, borderWidth: 2, borderDash: [6, 4], pointRadius: (c) => (c.dataIndex === n ? 5 : 0), spanGaps: true },
        ],
      },
      options: {
        interaction: { mode: "nearest", axis: "x", intersect: false },
        scales: { x: xCat(), y: { min: 0, max: 1, ticks: { ...pctTicks(), stepSize: 0.25 } } },
        plugins: {
          legend: { display: false },
          marks: { lines: [{ at: 0.5, color: C.muted, dash: [4, 4], width: 1 }] },
          tooltip: {
            filter: (i) => i.datasetIndex === 0 || (i.datasetIndex === 3 && i.dataIndex === n),
            callbacks: {
              label: (c) => (c.datasetIndex === 0 ? fill(t.cards.forecast.tipHistory, { v: pct(c.raw), n: num(s.historyN[c.dataIndex + start]) }) : fill(t.cards.forecast.tipForecast, { pred: pct(s.pred), lo: pct(s.low), hi: pct(s.high) })),
              footer: (items) => (items.some((i) => i.datasetIndex === 3) && s.mae != null ? fill(t.cards.forecast.tipBacktest, { mae: pct(s.mae), naive: pct(s.naive) }) : ""),
            },
          },
        },
      },
    },
    dim: false,
    finding: s.ok ? fill(t.cards.forecast.finding, { sector: s.sector, pred: pct(s.pred), p: prob(s.p) }) : fill(t.cards.forecast.findingEmpty, { sector: s.sector, n: s.observed }),
    overlays: (chart) => {
      const a = chart.chartArea;
      const y = chart.scales.y;
      const out = [
        { key: "half", kind: "tag", x: a.left + 4, y: y.getPixelForValue(0.5) - 2, place: "above-right", text: t.cards.forecast.half },
        { key: "window", kind: "tag", x: a.right - 2, y: a.top + 2, place: "below-left", text: fill(t.cards.forecast.window, { n }) },
      ];
      const low = s.pred < 0.5;
      if (s.ok) out.push({ key: "pred", kind: "callout", tone: s.reliable ? "ink" : "warn", x: chart.scales.x.getPixelForValue(n) - 8, y: y.getPixelForValue(s.pred) + (low ? -10 : 10), place: low ? "above-left" : "below-left", text: fill(t.cards.forecast.predicted, { arrow: trend(s.slope), pred: pct(s.pred, 0) }), sub: fill(t.cards.forecast.chance, { p: prob(s.p) }) });
      return out;
    },
    steps: [
      { target: { el: [0, Math.max(0, last)] }, text: t.cards.forecast.steps[0] },
      { target: { y: 0.5 }, text: t.cards.forecast.steps[1] },
      { target: { el: [3, n] }, text: t.cards.forecast.steps[2] },
      { target: { at: [n, s.low ?? 0, s.high ?? 1] }, text: t.cards.forecast.steps[3] },
    ],
  };
}

export function fruitsSpec(s) {
  const win = s.winners.indexOf(true);
  return {
    config: {
      type: "bar",
      data: {
        labels: s.labels.map(fruitName),
        datasets: [{ label: t.charts.count, data: s.values, backgroundColor: s.winners.map((w) => (w ? C.up : alpha(C.up, 0.28))), hoverBackgroundColor: C.up, borderRadius: 6, barPercentage: 0.62 }],
      },
      options: {
        indexAxis: "y",
        scales: { x: { beginAtZero: true, grace: "45%", ticks: { callback: (v) => num(v), maxTicksLimit: narrow() ? 3 : 6 } }, y: { grid: { display: false } } },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => fill(t.cards.fruits.tip, { n: num(c.raw), share: pct(s.shares[c.dataIndex]) }) } } },
      },
    },
    finding: s.tie ? t.cards.fruits.findingTie : win >= 0 ? fill(t.cards.fruits.finding, { fruit: fruitName(s.labels[win]), n: num(s.values[win]), share: pct(s.shares[win]) }) : t.dashboard.noData,
    overlays: (chart) =>
      s.values
        .map((v, i) => {
          const r = elRect(chart, 0, i);
          if (!r) return null;
          return { key: `v${i}`, kind: s.winners[i] ? "callout" : "value", tone: s.winners[i] ? "ink" : "", x: r.right + 8, y: (r.top + r.bottom) / 2, place: "right", text: `${num(v)} · ${pct(s.shares[i], 0)}`, sub: s.winners[i] ? (s.tie ? t.cards.fruits.tie : t.cards.fruits.winner) : "" };
        })
        .filter(Boolean),
    steps: [
      { target: { el: [0, Math.max(0, win)] }, text: t.cards.fruits.steps[0] },
      { target: { area: "x" }, text: t.cards.fruits.steps[1] },
      { target: { selector: ".n-badge" }, text: t.cards.fruits.steps[2] },
    ],
  };
}

export function growthSpec(s, kind, range, period) {
  const labels = s.labels.map((l) => periodLabel(l, period));
  const up = s.sign.indexOf(1);
  const down = s.sign.indexOf(-1);
  const name = kind === "good" ? t.charts.good : t.charts.rotten;
  return {
    config: {
      type: "bar",
      data: {
        labels,
        datasets: [
          { type: "bar", label: t.cards.growth.countLabel, data: s.count, backgroundColor: s.sign.map((v) => (v >= 0 ? C.up : C.down)), borderRadius: 3, barPercentage: 0.82, categoryPercentage: 0.9, order: 2 },
          { type: "line", label: t.cards.growth.prop, data: s.prop, borderColor: alpha(C.ink, 0.55), borderWidth: 1.2, borderDash: [5, 4], pointRadius: 0, pointHoverRadius: 3, spanGaps: false, order: 1 },
        ],
      },
      options: {
        interaction: { mode: "index", intersect: false },
        scales: { x: xCat(), y: { min: range.min, max: range.max, ticks: pctTicks(), grid: zeroGrid(0) } },
        plugins: {
          legend: {
            onClick: () => {},
            labels: {
              generateLabels: () => [
                { text: t.cards.growth.up, fillStyle: C.up, strokeStyle: C.up, lineWidth: 0, datasetIndex: 0 },
                { text: t.cards.growth.down, fillStyle: C.down, strokeStyle: C.down, lineWidth: 0, datasetIndex: 0 },
                { text: t.cards.growth.prop, fillStyle: "rgba(0,0,0,0)", strokeStyle: C.ink, lineWidth: 1.5, lineDash: [4, 3], datasetIndex: 1 },
              ],
            },
          },
          tooltip: {
            callbacks: {
              label: (c) => `${c.dataset.label}: ${c.raw == null ? t.charts.na : signedPct(c.raw)}`,
              footer: (items) => fill(t.charts.nFruits, { n: num(s.n[items[0].dataIndex]) }),
            },
          },
        },
      },
    },
    finding: s.last ? fill(t.cards.growth.finding, { kind: name, value: signedPct(s.last.value), label: labels[s.last.index] }) : t.cards.growth.findingNone,
    overlays: (chart) => {
      const zero = chart.scales.y.getPixelForValue(0);
      const out = s.na.map((i) => na(chart, i, zero - 2));
      const r = s.last && elRect(chart, 0, s.last.index);
      if (r) {
        const pos = s.last.value >= 0;
        out.push({ key: "last", kind: "callout", tone: pos ? "up" : "down", x: (r.left + r.right) / 2, y: pos ? r.top - 4 : r.bottom + 4, place: pos ? "above" : "below", text: `${arrow(s.last.value)} ${signedPct(s.last.value)}`, sub: labels[s.last.index] });
      }
      return out;
    },
    steps: [
      { target: { y: 0 }, text: t.cards.growth.steps[0] },
      { target: up >= 0 ? { el: [0, up] } : { area: "chart" }, text: t.cards.growth.steps[1] },
      { target: down >= 0 ? { el: [0, down] } : { area: "chart" }, text: t.cards.growth.steps[2] },
      { target: { selector: ".o-na" }, text: t.cards.growth.steps[3] },
    ],
  };
}

export function bucketLabel(which, b) {
  return which === "month" ? t.months[Number(b) - 1] : which === "season" ? t.seasons[b] || b : `S${b}`;
}

export function recurringSpec(s, which) {
  const labels = s.buckets.map((b) => bucketLabel(which, b));
  const bars = (values, peak, color) => values.map((_, i) => (i === peak ? color : alpha(color, 0.35)));
  const callout = (chart, d, i, values, tone, kind) => {
    const r = i >= 0 && elRect(chart, d, i);
    if (!r) return null;
    const pos = values[i] >= 0;
    return { key: `peak${d}`, kind: "callout", tone, x: (r.left + r.right) / 2, y: pos ? r.top - 4 : r.bottom + 4, place: pos ? "above" : "below", text: `${labels[i]} ${signedPct(values[i])}`, sub: fill(t.cards.recurring.peak, { kind }) };
  };
  return {
    config: {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: t.charts.good, data: s.good, backgroundColor: bars(s.good, s.peakGood, C.good), hoverBackgroundColor: C.good, borderRadius: 3 },
          { label: t.charts.rotten, data: s.rotten, backgroundColor: bars(s.rotten, s.peakRotten, C.rotten), hoverBackgroundColor: C.rotten, borderRadius: 3 },
        ],
      },
      options: {
        scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, autoSkipPadding: 8 } }, y: { ticks: pctTicks(), grid: zeroGrid(0), grace: "12%" } },
        plugins: {
          legend: legendFull([[t.charts.good, C.good], [t.charts.rotten, C.rotten]]),
          tooltip: {
            callbacks: {
              label: (c) => `${c.dataset.label}: ${c.raw == null ? t.charts.na : signedPct(c.raw)}`,
              footer: (items) => fill(t.charts.nPeriods, { n: num((items[0].datasetIndex ? s.rottenN : s.goodN)[items[0].dataIndex]) }),
            },
          },
        },
      },
    },
    finding: s.peakRotten >= 0 ? fill(t.cards.recurring.finding, { view: t.cards.recurring.tabs[which], rot: labels[s.peakRotten], rv: signedPct(s.rotten[s.peakRotten]), good: labels[s.peakGood] ?? "—", gv: signedPct(s.good[s.peakGood]) }) : t.dashboard.noData,
    overlays: (chart) => [callout(chart, 1, s.peakRotten, s.rotten, "rotten", t.charts.rotten.toLowerCase()), s.peakGood !== s.peakRotten ? callout(chart, 0, s.peakGood, s.good, "good", t.charts.good.toLowerCase()) : null].filter(Boolean),
    steps: [
      { target: { selector: ".seg-tabs" }, text: t.cards.recurring.steps[0] },
      { target: s.peakRotten >= 0 ? { el: [1, s.peakRotten] } : { area: "chart" }, text: t.cards.recurring.steps[1] },
      { target: s.peakGood >= 0 ? { el: [0, s.peakGood] } : { area: "chart" }, text: t.cards.recurring.steps[2] },
      { target: { selector: ".n-badge" }, text: t.cards.recurring.steps[3] },
    ],
  };
}

export function gaussianSpecs(s) {
  const poor = s.flagged;
  const bands = [
    { from: s.sigma2[0], to: s.sigma2[1], color: alpha(C.up, 0.07) },
    { from: s.sigma1[0], to: s.sigma1[1], color: alpha(C.up, 0.13) },
  ];
  if (s.range[0] < 0) bands.push({ from: s.range[0], to: 0, color: hatch("rgba(207, 224, 214, 0.28)") });
  if (s.range[1] > 1) bands.push({ from: 1, to: s.range[1], color: hatch("rgba(207, 224, 214, 0.28)") });
  const tallest = s.bins.reduce((k, b, i) => (b.y > s.bins[k].y ? i : k), 0);
  const stamp = (chart) => ({ key: "stamp", kind: "stamp", x: chart.chartArea.right - 4, y: chart.chartArea.top + 4, place: "below-left", text: t.cards.gaussian.poor, sub: s.shapiroP != null ? fill(t.cards.gaussian.poorSub, { p: dec(s.shapiroP) }) : "" });
  const hist = {
    config: {
      type: "bar",
      data: {
        datasets: [
          { type: "bar", label: t.cards.gaussian.hist, data: s.bins.map((b) => ({ x: b.x, y: b.y })), backgroundColor: alpha(C.hist, 0.55), hoverBackgroundColor: C.hist, borderColor: C.hist, borderWidth: 1, barPercentage: 1, categoryPercentage: 1, order: 2 },
          { type: "line", label: t.cards.gaussian.pdf, data: s.curve, borderColor: poor ? C.muted : C.rotten, borderDash: poor ? [6, 5] : [], borderWidth: poor ? 1.5 : 2.5, pointRadius: 0, tension: 0.35, order: 1 },
        ],
      },
      options: {
        scales: {
          x: { type: "linear", offset: false, min: s.range[0], max: s.range[1], ticks: { callback: (v) => pct(v, 0), maxTicksLimit: narrow() ? 4 : 6 }, grid: { color: (c) => (c.tick?.value === 0 || c.tick?.value === 1 ? C.muted : C.grid) } },
          y: { beginAtZero: true, ticks: { display: false }, title: { display: true, text: t.charts.frequency } },
        },
        plugins: {
          legend: { position: "bottom" },
          marks: { bands, lines: [{ axis: "x", at: s.mean, color: C.ink, width: 1.5 }] },
          tooltip: {
            filter: (i) => i.datasetIndex === 0,
            callbacks: {
              title: () => s.sector,
              label: (c) => fill(t.cards.gaussian.tipBin, { from: pct(s.bins[c.dataIndex].x - s.bins[c.dataIndex].width / 2), to: pct(s.bins[c.dataIndex].x + s.bins[c.dataIndex].width / 2), n: num(s.bins[c.dataIndex].count) }),
              footer: () => fill(t.charts.nPeriods, { n: num(s.n) }),
            },
          },
        },
      },
    },
    dim: false,
    finding: fill(t.cards.gaussian.finding, { sector: s.sector, mean: pct(s.mean), std: pct(s.std), n: s.n }) + (poor ? ` ${t.cards.gaussian.findingPoor}` : ""),
    overlays: (chart) => {
      const x = chart.scales.x;
      const a = chart.chartArea;
      const out = [
        { key: "mean", kind: "callout", tone: "ink", x: x.getPixelForValue(s.mean), y: a.top + (poor && x.getPixelForValue(s.mean) > a.right - 190 ? 46 : 2), place: "below", text: fill(t.cards.gaussian.mean, { v: pct(s.mean) }) },
        { key: "s1", kind: "tag", x: x.getPixelForValue(s.sigma1[1]) + 3, y: a.bottom - 4, place: "above-right", text: t.cards.gaussian.s1 },
        { key: "s2", kind: "tag", x: x.getPixelForValue(s.sigma2[1]) + 3, y: a.bottom - 22, place: "above-right", text: t.cards.gaussian.s2 },
      ];
      if (s.range[0] < 0) out.push({ key: "imp", kind: "tag", x: (a.left + x.getPixelForValue(0)) / 2, y: a.bottom - 4, place: "above", text: t.cards.gaussian.impossible });
      if (poor) out.push(stamp(chart));
      return out;
    },
    steps: [
      { target: { el: [0, tallest] }, text: t.cards.gaussian.steps[0] },
      { target: { x: s.mean }, text: t.cards.gaussian.steps[1] },
      { target: { xRange: s.sigma1 }, text: t.cards.gaussian.steps[2] },
      { target: { chart: 1, area: "chart" }, text: t.cards.gaussian.steps[3] },
    ],
  };
  const qq = {
    config: {
      type: "scatter",
      data: {
        datasets: [
          { label: t.charts.observed, data: s.qq, backgroundColor: poor ? C.rotten : C.up, pointRadius: 3, pointHoverRadius: 5 },
          { type: "line", label: t.cards.gaussian.qqLine, data: s.qqLine, borderColor: C.ink, borderWidth: 1.5, pointRadius: 0 },
        ],
      },
      options: {
        scales: { x: { title: { display: true, text: t.charts.theoretical } }, y: { ticks: pctTicks() } },
        plugins: { legend: { display: false }, tooltip: { filter: (i) => i.datasetIndex === 0, callbacks: { label: (c) => `${t.charts.observed}: ${pct(c.raw.y)}`, footer: () => fill(t.charts.nPeriods, { n: num(s.n) }) } } },
      },
    },
    dim: false,
    finding: fill(t.cards.gaussian.qqFinding, { sector: s.sector, w: dec(s.shapiroW), p: dec(s.shapiroP) }),
    overlays: (chart) => {
      const a = chart.chartArea;
      const out = [{ key: "line", kind: "tag", x: a.left + 4, y: a.top + 2, place: "below-right", text: t.cards.gaussian.qqLine }];
      if (poor) out.push({ ...stamp(chart), y: a.bottom - 4, place: "above-left" });
      return out;
    },
  };
  return { hist, qq };
}

export function overviewSpecs(s, period) {
  const labels = s.labels.map((l) => periodLabel(l, period));
  const last = lastIndex(s.rate);
  const counter = (key, value, format, label) => (chart) => [{ key, kind: "counter", value, format, x: chart.chartArea.left, y: 0, place: "below-right", text: label }];
  const head = { padding: { top: 48 } };
  const volume = {
    config: {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: t.charts.good, data: s.good, backgroundColor: C.good, stack: "s", borderRadius: 2, categoryPercentage: 0.9 },
          { label: t.charts.rotten, data: s.rotten, backgroundColor: C.rotten, stack: "s", borderRadius: 2, categoryPercentage: 0.9 },
        ],
      },
      options: {
        layout: head,
        interaction: { mode: "index", intersect: false },
        scales: { x: { stacked: true, ...xCat() }, y: { stacked: true, beginAtZero: true, ticks: { callback: (v) => num(v), maxTicksLimit: 4 } } },
        plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${num(c.raw)}`, footer: (items) => fill(t.charts.nFruits, { n: num(s.totals[items[0].dataIndex]) }) } } },
      },
    },
    finding: fill(t.cards.overview.findingVolume, { n: num(s.total) }),
    overlays: counter("total", s.total, num, t.cards.overview.total),
  };
  const rate = {
    config: {
      type: "line",
      data: { labels, datasets: [{ label: t.cards.overview.rate, data: s.rate, borderColor: C.rotten, backgroundColor: fade(C.rotten), fill: "origin", borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.3, spanGaps: false }] },
      options: {
        layout: head,
        interaction: { mode: "index", intersect: false },
        scales: { x: xCat(), y: { beginAtZero: true, grace: "10%", ticks: { ...pctTicks(), maxTicksLimit: 4 } } },
        plugins: { legend: { display: false }, marks: { lines: [{ at: s.rottenRate, color: C.ink, dash: [4, 4], width: 1 }] }, tooltip: { callbacks: { label: (c) => `${t.cards.overview.rate}: ${pct(c.raw)}`, footer: (items) => fill(t.charts.nFruits, { n: num(s.totals[items[0].dataIndex]) }) } } },
      },
    },
    finding: fill(t.cards.overview.findingRate, { v: pct(s.rottenRate) }),
    overlays: (chart) => {
      const out = counter("rate", s.rottenRate, (v) => pct(v), t.cards.overview.rateCounter)(chart);
      out.push({ key: "avg", kind: "tag", x: chart.chartArea.right - 4, y: chart.scales.y.getPixelForValue(s.rottenRate) - 2, place: "above-left", text: t.cards.overview.avg });
      return out;
    },
  };
  const sectors = {
    config: {
      type: "bar",
      data: { labels: s.sectors, datasets: [{ label: t.cards.overview.rate, data: s.sectorRates, backgroundColor: s.sectorRates.map((_, i) => (i === 0 ? C.rotten : alpha(C.rotten, 0.32))), hoverBackgroundColor: C.rotten, borderRadius: 5, barPercentage: 0.66 }] },
      options: {
        indexAxis: "y",
        layout: head,
        scales: { x: { beginAtZero: true, grace: "25%", ticks: { ...pctTicks(), maxTicksLimit: 4 } }, y: { grid: { display: false } } },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${t.cards.overview.rate}: ${pct(c.raw)}`, footer: (items) => fill(t.charts.nFruits, { n: num(s.sectorN[items[0].dataIndex]) }) } } },
      },
    },
    finding: s.sectors.length ? fill(t.cards.overview.findingSectors, { sector: s.sectors[0], v: pct(s.sectorRates[0]) }) : t.dashboard.noData,
    overlays: (chart) => {
      const out = counter("count", s.sectors.length, num, t.cards.overview.sectorsCounter)(chart);
      s.sectorRates.forEach((v, i) => {
        const r = elRect(chart, 0, i);
        if (r) out.push({ key: `s${i}`, kind: i === 0 ? "callout" : "value", tone: i === 0 ? "rotten" : "", x: r.right + 6, y: (r.top + r.bottom) / 2, place: "right", text: pct(v) });
      });
      return out;
    },
  };
  return {
    volume,
    rate,
    sectors,
    steps: [
      { target: { chart: 0, area: "chart" }, text: t.cards.overview.steps[0] },
      { target: last >= 0 ? { chart: 1, el: [0, last] } : { chart: 1, area: "chart" }, text: t.cards.overview.steps[1] },
      { target: { chart: 2, el: [0, 0] }, text: t.cards.overview.steps[2] },
      { target: { selector: ".n-badge" }, text: t.cards.overview.steps[3] },
    ],
  };
}
