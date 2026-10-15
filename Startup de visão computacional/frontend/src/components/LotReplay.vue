<script setup>
import "../control.css";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { api } from "../api.js";
import { vTrace } from "../control.js";
import { num, pct } from "../format.js";
import { reducedMotion } from "../media.js";
import { fill, t } from "../strings.js";

const props = defineProps({ replay: { type: Object, required: true } });

const T = t.control.replay;
const CATS = ["boa", "baixa_qualidade", "podre", "revisar"];
const TONE = { boa: "good", baixa_qualidade: "poor", podre: "rotten", revisar: "review" };
const SAMPLES = 240;

const data = ref(null);
const failed = ref(false);
const i = ref(0);
const playing = ref(false);
let cum = null;
let raf = 0;

const n = computed(() => data.value?.columns.id.length || 0);
const counts = computed(() => Object.fromEntries(CATS.map((c) => [c, cum ? cum[c][i.value] : 0])));
const decided = computed(() => counts.value.boa + counts.value.baixa_qualidade + counts.value.podre);
const share = computed(() => (decided.value ? counts.value.podre / decided.value : null));
const clock = (ms) => new Date(ms).toLocaleTimeString("pt-BR");
const when = computed(() => (n.value ? clock(data.value.columns.timestamp[Math.max(0, i.value - 1)]) : "—"));
const path = ref("");
const top = ref(1);
const scope = computed(() => (props.replay.since ? fill(T.window, { from: props.replay.since.slice(11, 16), to: props.replay.until.slice(11, 16) }) : T.whole));
const trace = computed(() => fill(t.control.history.trace, { filter: `lote ${props.replay.lot} · ${props.replay.camera} · ${scope.value} · fonte ${props.replay.source}`, n: num(data.value?.total ?? 0) }));

function build(col) {
  const total = col.id.length;
  cum = Object.fromEntries(CATS.map((c) => [c, new Int32Array(total + 1)]));
  for (let k = 0; k < total; k++) {
    const cat = col.needs_review[k] ? "revisar" : CATS.includes(col.label[k]) ? col.label[k] : "revisar";
    for (const c of CATS) cum[c][k + 1] = cum[c][k] + (c === cat ? 1 : 0);
  }
  const raw = [];
  for (let s = 1; s <= SAMPLES; s++) {
    const k = Math.round((s / SAMPLES) * total);
    const d = cum.boa[k] + cum.baixa_qualidade[k] + cum.podre[k];
    if (d) raw.push([k / total, cum.podre[k] / d]);
  }
  top.value = Math.max(0.05, ...raw.map((r) => r[1])) * 1.15;
  const pts = raw.map(([x, y]) => `${(x * 100).toFixed(2)},${(40 - (y / top.value) * 40).toFixed(2)}`);
  path.value = pts.length ? `M ${pts.join(" L ")}` : "";
}

async function load() {
  const r = props.replay;
  const query = { source: r.source || "all", kind: "camera", camera: r.camera, lot: r.lot, order: "asc", shape: "columns", size: 20000 };
  if (r.since) Object.assign(query, { since: r.since, until: r.until });
  try {
    data.value = await api("/api/events", { query });
    build(data.value.columns);
    i.value = reducedMotion() ? n.value : 0;
  } catch {
    failed.value = true;
  }
}

function stop() {
  cancelAnimationFrame(raf);
  playing.value = false;
}

function play() {
  if (playing.value) return stop();
  if (reducedMotion()) {
    i.value = n.value;
    return;
  }
  if (i.value >= n.value) i.value = 0;
  playing.value = true;
  const start = i.value;
  const t0 = performance.now();
  const ms = 6000 * (1 - start / Math.max(n.value, 1));
  raf = requestAnimationFrame(function step(now) {
    const k = Math.min(1, (now - t0) / Math.max(ms, 1));
    i.value = Math.round(start + (n.value - start) * k);
    if (k < 1) raf = requestAnimationFrame(step);
    else playing.value = false;
  });
}

onMounted(load);
onBeforeUnmount(stop);
</script>

<template>
  <div class="replay">
    <p class="hint">{{ T.note }} {{ scope }}.</p>
    <p v-if="failed" class="notice error" role="alert">{{ t.control.inspector.loadFail }}</p>
    <p v-else-if="!data" class="hint">{{ T.loading }}</p>
    <template v-else>
      <p v-if="data.demo" class="chip" data-state="demo">{{ t.control.chips.demo }}</p>
      <div class="replay-controls">
        <button class="btn btn-primary btn-sm" type="button" :aria-pressed="playing" @click="play">{{ playing ? T.pause : T.play }}</button>
        <button class="btn btn-secondary btn-sm" type="button" @click="stop(); i = 0">{{ T.restart }}</button>
      </div>
      <label class="field replay-scrub">
        <span>{{ T.position }}</span>
        <input v-model.number="i" type="range" min="0" :max="n" step="1" :aria-valuetext="fill(T.progress, { i: num(i), n: num(n), time: when })" @input="stop" />
      </label>
      <p class="replay-pos num" aria-live="off">{{ fill(T.progress, { i: num(i), n: num(n), time: when }) }}</p>
      <p class="replay-static num" v-trace="trace">{{ fill(T.final, { n: num(data.total) }) }}</p>
      <h3 class="replay-sub">{{ T.counts }}</h3>
      <ul class="replay-counts">
        <li v-for="c in CATS" :key="c" :class="TONE[c]" :data-cat="c">
          <span class="replay-name">{{ t.classes[c] }}</span>
          <span class="prob-bar" aria-hidden="true"><span :style="{ transform: `scaleX(${i ? counts[c] / i : 0})` }"></span></span>
          <strong class="num" v-trace="trace">{{ num(counts[c]) }}</strong>
        </li>
      </ul>
      <h3 class="replay-sub">{{ T.share }}: <span class="num replay-share">{{ share == null ? "—" : pct(share) }}</span></h3>
      <p class="hint num">0% – {{ pct(top, 0) }}</p>
      <svg class="replay-line" viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
        <defs><clipPath id="replay-clip"><rect x="0" y="0" width="100" height="40" :transform="`scale(${n ? i / n : 0}, 1)`" /></clipPath></defs>
        <path class="replay-ghost" :d="path" vector-effect="non-scaling-stroke" />
        <path class="replay-trace" :d="path" clip-path="url(#replay-clip)" vector-effect="non-scaling-stroke" />
      </svg>
    </template>
  </div>
</template>
