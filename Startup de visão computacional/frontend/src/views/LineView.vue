<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { api } from "../api.js";
import { C, Chart, alpha } from "../charts.js";
import BackgroundVideo from "../components/BackgroundVideo.vue";
import CameraDiagram from "../components/CameraDiagram.vue";
import { num, pct } from "../format.js";
import { reducedMotion, vReveal } from "../media.js";
import { fill, t } from "../strings.js";

const SPANS = [30, 60, 240, 480, 1440];
const WINDOW = { 30: 1, 60: 1, 240: 5, 480: 15, 1440: 60 };
const CLASSES = ["boa", "baixa_qualidade", "podre", "revisar"];
const COLORS = { boa: C.good, baixa_qualidade: C.poor, podre: C.rotten, revisar: C.review };

const cameras = ref([]);
const slug = ref("");
const minutes = ref(60);
const source = ref("demo");
const summary = ref(null);
const loading = ref(false);
const failed = ref("");
const frameTick = ref(0);
const flowCanvas = ref(null);
const pCanvas = ref(null);
let flowChart = null;
let pChart = null;
let summaryTimer = 0;
let frameTimer = 0;

const cam = computed(() => cameras.value.find((c) => c.slug === slug.value));
const status = computed(() => summary.value?.status || cam.value?.status || { online: false });
const frameUrl = computed(() => `/api/cameras/${slug.value}/frame?t=${frameTick.value}`);
const decided = computed(() => (summary.value ? CLASSES.slice(0, 3).reduce((s, c) => s + summary.value.counts[c], 0) : 0));
const kpis = computed(() => {
  const s = summary.value;
  if (!s || !s.total) return [];
  return [
    { key: "throughput", value: s.throughput_per_min == null ? "—" : num(Math.round(s.throughput_per_min * 10) / 10), sub: fill(t.line.kpi.total, { n: num(s.total) }) },
    ...["boa", "baixa_qualidade", "podre"].map((c) => ({ key: c, value: pct(s.shares[c].share), sub: s.shares[c].ci95[0] == null ? "" : fill(t.line.kpi.ci, { lo: pct(s.shares[c].ci95[0]), hi: pct(s.shares[c].ci95[1]) }), tone: c })),
    { key: "revisar", value: pct(s.review_share), sub: num(s.counts.revisar), tone: "revisar" },
  ];
});
const alarmList = computed(() => {
  const s = summary.value;
  if (!s) return [];
  return s.p_chart.alarms.map((a) => ({ ...a, text: fill(t.line.alarmText[a.rule], { time: clock(s.windows[a.index].start), p: pct(s.p_chart.p[a.index]) }) }));
});
const sizeText = computed(() => {
  const z = summary.value?.size_mm;
  return z ? fill(t.line.size, { m: num(Math.round(z.median)), lo: num(Math.round(z.p10)), hi: num(Math.round(z.p90)) }) : "";
});

function clock(iso) {
  return iso.slice(11, 16);
}

async function loadCameras() {
  cameras.value = (await api("/api/cameras")).cameras;
  if (cameras.value.some((c) => c.status.online && c.status.source === "câmera")) source.value = "real";
  if (!slug.value && cameras.value.length) slug.value = cameras.value[0].slug;
}

async function loadSummary() {
  if (!slug.value || loading.value) return;
  loading.value = true;
  try {
    summary.value = await api("/api/line", { query: { camera: slug.value, minutes: minutes.value, window: WINDOW[minutes.value], source: source.value } });
    failed.value = "";
    draw();
  } catch (err) {
    failed.value = err.message || "erro";
  } finally {
    loading.value = false;
  }
}

function draw() {
  const s = summary.value;
  if (!s || !flowCanvas.value || !pCanvas.value) return;
  const labels = s.windows.map((w) => clock(w.start));
  const animation = reducedMotion() ? false : { duration: 500 };
  const flow = {
    labels,
    datasets: CLASSES.map((c) => ({ label: t.classes[c], data: s.windows.map((w) => w[c]), backgroundColor: COLORS[c], borderRadius: 2, stack: "n" })),
  };
  if (flowChart) {
    flowChart.data = flow;
    flowChart.update(animation ? undefined : "none");
  } else {
    flowChart = new Chart(flowCanvas.value, {
      type: "bar",
      data: flow,
      options: { animation, scales: { x: { stacked: true, grid: { display: false }, ticks: { maxTicksLimit: 8 } }, y: { stacked: true, beginAtZero: true, title: { display: true, text: t.line.fruitsAxis } } }, plugins: { legend: { position: "bottom" } } },
    });
  }
  const pc = s.p_chart;
  const alarmIdx = new Set(pc.alarms.map((a) => a.index));
  const pData = {
    labels,
    datasets: [
      { label: t.line.ucl, data: pc.ucl, borderColor: alpha(C.rotten, 0.8), backgroundColor: alpha(C.rotten, 0.08), borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0, stepped: "middle", fill: "start" },
      { label: t.line.center, data: labels.map(() => pc.center), borderColor: C.muted, borderWidth: 1, borderDash: [2, 3], pointRadius: 0 },
      { label: t.line.kpi.podre, data: pc.p, borderColor: C.ink, backgroundColor: pc.p.map((_, i) => (alarmIdx.has(i) ? C.rotten : C.ink)), pointStyle: pc.p.map((_, i) => (alarmIdx.has(i) ? "rectRot" : "circle")), pointRadius: pc.p.map((_, i) => (alarmIdx.has(i) ? 7 : 3)), borderWidth: 1.5 },
    ],
  };
  if (pChart) {
    pChart.data = pData;
    pChart.update(animation ? undefined : "none");
  } else {
    pChart = new Chart(pCanvas.value, {
      type: "line",
      data: pData,
      options: { animation, scales: { y: { beginAtZero: true, ticks: { callback: (v) => pct(v, 0) } }, x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } } }, plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${pct(c.raw)}` } } } },
    });
  }
}

function restart() {
  clearInterval(summaryTimer);
  clearInterval(frameTimer);
  loadSummary();
  summaryTimer = setInterval(loadSummary, 15000);
  frameTimer = setInterval(() => {
    if (status.value.online) frameTick.value += 1;
  }, 1000);
}

watch([slug, minutes, source], () => {
  summary.value = null;
  restart();
});

onMounted(async () => {
  try {
    await loadCameras();
  } catch (err) {
    failed.value = err.message || "erro";
  }
  restart();
});

onBeforeUnmount(() => {
  clearInterval(summaryTimer);
  clearInterval(frameTimer);
  flowChart?.destroy();
  pChart?.destroy();
});
</script>

<template>
  <section class="page line-page">
    <header class="page-head page-banner hero">
      <BackgroundVideo id="bg-esteira-simulada" />
      <div class="banner-text page-head-text">
        <h1>{{ t.line.title }}</h1>
        <p class="lead">{{ t.line.lead }}</p>
        <p class="hero-caption"><span class="badge sim">{{ t.line.simulated }}</span>{{ t.line.heroCaption }}</p>
      </div>
      <div class="page-head-actions">
        <a class="btn btn-secondary" href="#camera">{{ t.line.ctaHow }}</a>
      </div>
    </header>

    <section id="linha" class="section monitor">
      <header class="section-head monitor-head">
        <div>
          <h2>{{ t.line.monitorTitle }}</h2>
          <p class="muted">{{ t.line.monitorLead }}</p>
        </div>
        <div class="monitor-controls">
          <label class="field">
            <span>{{ t.line.camera }}</span>
            <select v-model="slug">
              <option v-for="c in cameras" :key="c.slug" :value="c.slug">{{ c.name }}</option>
            </select>
          </label>
          <label class="field">
            <span>{{ t.line.period }}</span>
            <select v-model.number="minutes">
              <option v-for="m in SPANS" :key="m" :value="m">{{ t.line.periods[m] }}</option>
            </select>
          </label>
          <label class="field">
            <span>{{ t.line.data }}</span>
            <select v-model="source">
              <option v-for="(label, key) in t.line.sources" :key="key" :value="key">{{ label }}</option>
            </select>
          </label>
        </div>
      </header>

      <p v-if="failed" class="notice error" role="alert">{{ t.line.failed }}</p>
      <p v-if="summary?.demo" class="notice info demo-note"><span class="badge demo">{{ t.line.demoBadge }}</span>{{ t.app.demoBadgeHint }}</p>

      <div class="monitor-grid">
        <figure class="live paper" :data-online="status.online ? 'yes' : 'no'">
          <div class="live-frame">
            <img v-if="status.online" :src="frameUrl" :alt="fill(t.line.frameAlt, { name: cam?.name || slug })" width="960" height="540" />
            <div v-else class="live-off">
              <svg width="42" height="42" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h3l2-3h8l2 3h3v12H3z" /><path d="m4 4 16 16" /></svg>
              <strong>{{ t.line.offline }}</strong>
              <code>{{ fill(t.line.offlineHelp, { slug }) }}</code>
            </div>
            <span class="live-pill" :class="status.online ? 'on' : 'off'">{{ status.online ? (status.source === "simulação" ? t.line.simulated : t.line.online) : t.line.offline }}</span>
          </div>
          <figcaption v-if="status.online" class="live-meta">{{ fill(t.line.frameMeta, { fps: status.fps, passages: num(status.passages), decider: status.decider }) }}</figcaption>
        </figure>

        <div class="kpis" aria-live="polite">
          <div v-for="k in kpis" :key="k.key" class="kpi paper" :class="k.tone ? `tone-${k.tone}` : ''">
            <span class="kpi-label">{{ t.line.kpi[k.key] }}</span>
            <strong class="kpi-value">{{ k.value }}</strong>
            <span class="kpi-sub">{{ k.sub }}</span>
          </div>
          <p v-if="summary && !summary.total" class="notice kpi-empty">{{ t.line.empty }}<br /><code v-if="source !== 'real'">{{ t.line.emptyDemo }}</code></p>
          <p v-if="sizeText" class="kpi-size muted">{{ sizeText }}</p>
        </div>
      </div>

      <div class="monitor-charts">
        <section class="paper chart-panel">
          <h3>{{ fill(t.line.flowTitle, { w: WINDOW[minutes] }) }}</h3>
          <p class="muted small">{{ t.line.flowSub }}</p>
          <div class="line-chart"><canvas ref="flowCanvas" role="img" :aria-label="t.line.flowSub"></canvas></div>
        </section>
        <section class="paper chart-panel">
          <h3>{{ t.line.chartTitle }}</h3>
          <p class="muted small">{{ t.line.chartSub }}</p>
          <div class="line-chart"><canvas ref="pCanvas" role="img" :aria-label="t.line.chartSub"></canvas></div>
          <h4>{{ t.line.alarms }}</h4>
          <ul v-if="alarmList.length" class="alarm-list">
            <li v-for="a in alarmList" :key="`${a.index}-${a.rule}`" :class="a.rule">{{ a.text }}</li>
          </ul>
          <p v-else class="muted small">{{ t.line.noAlarms }}</p>
        </section>
      </div>

      <section class="paper lots-panel">
        <h3>{{ t.line.lotsTitle }}</h3>
        <p class="muted small">{{ fill(t.line.lotsSub, { max: summary?.max_rotten == null ? "—" : pct(summary.max_rotten, 0) }) }}</p>
        <div v-if="summary?.lots.length" class="lots-scroll" role="region" tabindex="0" :aria-label="t.line.lotsTitle">
          <table class="lots">
            <thead>
              <tr>
                <th v-for="(label, key) in t.line.lotCols" :key="key" scope="col">{{ label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="l in summary.lots" :key="l.lot">
                <th scope="row">{{ l.lot }}<span class="lot-time">{{ clock(l.first) }}–{{ clock(l.last) }}</span></th>
                <td>{{ num(l.n) }}</td>
                <td>{{ pct(l.rotten.share) }} <span class="muted">({{ pct(l.rotten.ci95[0]) }}–{{ pct(l.rotten.ci95[1]) }})</span></td>
                <td>{{ pct(l.poor.share) }}</td>
                <td><span class="verdict-pill" :class="l.verdict">{{ t.line.verdicts[l.verdict] || "—" }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted small">{{ t.line.lotsEmpty }}</p>
      </section>
    </section>

    <section id="camera" class="section camera-section">
      <header class="section-head">
        <h2>{{ t.line.cameraTitle }}</h2>
        <p class="muted">{{ t.line.cameraLead }}</p>
      </header>
      <div class="camera-grid">
        <CameraDiagram v-reveal />
        <ol class="camera-steps">
          <li v-for="(s, i) in t.line.steps" :key="s.title" v-reveal class="camera-step" :class="{ ai: i === 3 }">
            <span class="step-num" aria-hidden="true">{{ i + 1 }}</span>
            <div>
              <h3>{{ s.title }}<span v-if="i === 3" class="badge ai">IA</span></h3>
              <p>{{ s.text }}</p>
            </div>
          </li>
        </ol>
      </div>
    </section>
  </section>
</template>
