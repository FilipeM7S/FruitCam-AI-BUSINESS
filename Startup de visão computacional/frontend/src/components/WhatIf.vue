<script setup>
import "../control.css";
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { api } from "../api.js";
import { tween, vTrace } from "../control.js";
import { confidence, dec, num, pct } from "../format.js";
import { fill, t } from "../strings.js";

const props = defineProps({
  query: { type: Object, required: true },
  filter: { type: String, required: true },
  highlight: { type: Object, default: null },
  start: { type: Number, default: 0.8 },
});

const T = t.control.whatIf;
const KNOWN = ["boa", "baixa_qualidade", "podre"];
const TONE = { boa: "good", baixa_qualidade: "poor", podre: "rotten", revisar: "review" };
const data = ref(null);
const failed = ref(false);
const thr = ref(props.start);
const shown = reactive({});
const stops = {};
let request = 0;

const classes = computed(() => {
  const keys = Object.keys(data.value?.classes || {});
  return [...KNOWN.filter((k) => keys.includes(k)), ...keys.filter((k) => !KNOWN.includes(k)).sort()];
});
const total = computed(() => classes.value.reduce((s, c) => s + data.value.classes[c].n, 0));
const step = computed(() => Math.round(thr.value * (data.value?.steps || 100)));

const rows = computed(() => {
  if (!data.value || !total.value) return [];
  let simReview = 0;
  let storedReview = 0;
  const out = classes.value.map((c) => {
    const h = data.value.classes[c];
    const below = h.bins.slice(0, step.value).reduce((s, v) => s + v, 0);
    simReview += below;
    storedReview += h.stored_review;
    return { key: c, sim: h.n - below, stored: h.n - h.stored_review };
  });
  out.push({ key: "revisar", sim: simReview, stored: storedReview });
  return out;
});

const realText = computed(() => {
  const m = data.value?.model;
  if (!m) return "";
  return fill(T.real, { v: m.version, t: m.reject_below == null ? T.none : dec(m.reject_below, 2) });
});

const verdict = computed(() => {
  const h = props.highlight;
  if (!h || h.confidence == null) return "";
  const v = h.confidence < thr.value ? T.verdictReview : fill(T.verdictDecided, { label: (t.classes[h.label] || h.label).toLowerCase() });
  return fill(T.thisFruit, { c: confidence(h.confidence), t: dec(thr.value, 2), verdict: v });
});

const trace = computed(() => fill(T.trace, { filter: props.filter, n: num(total.value) }));

watch(rows, (list) => {
  for (const r of list) {
    stops[r.key]?.();
    stops[r.key] = tween(shown[r.key] ?? 0, r.sim, 350, (v) => (shown[r.key] = Math.round(v)));
  }
});

async function load() {
  const id = ++request;
  failed.value = false;
  try {
    const body = await api("/api/events/thresholds", { query: props.query });
    if (id === request) data.value = body;
  } catch {
    if (id === request) failed.value = true;
  }
}

watch(() => JSON.stringify(props.query), load, { immediate: true });
onBeforeUnmount(() => Object.values(stops).forEach((s) => s()));
defineExpose({ rows, thr });
</script>

<template>
  <section class="whatif instrument" :aria-label="T.title">
    <header class="whatif-head">
      <h3>{{ T.title }}</h3>
      <span class="chip" data-state="simulacao">{{ t.control.chips.simulacao }}</span>
      <span v-if="data?.demo" class="chip" data-state="demo">{{ t.control.chips.demo }}</span>
    </header>
    <p class="whatif-sim">{{ T.sim }}. {{ T.note }}</p>
    <p v-if="failed" class="notice error" role="alert">{{ t.control.inspector.loadFail }}</p>
    <template v-else-if="data">
      <div class="whatif-thresholds">
        <label class="field whatif-slider">
          <span>{{ T.threshold }}: <strong class="num whatif-value">{{ dec(thr, 2) }}</strong></span>
          <input v-model.number="thr" type="range" min="0" max="1" step="0.01" :aria-valuetext="dec(thr, 2)" />
        </label>
        <p class="whatif-real num">{{ realText }}</p>
      </div>
      <p v-if="verdict" class="whatif-fruit" role="status">{{ verdict }}</p>
      <p v-if="!total" class="hint">{{ T.empty }}</p>
      <table v-else class="whatif-table">
        <thead>
          <tr>
            <th scope="col"><span class="visually-hidden">{{ t.control.history.cols.label }}</span></th>
            <th scope="col">{{ T.stored }}</th>
            <th scope="col">{{ T.simulated }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.key" :class="TONE[r.key]" :data-class="r.key">
            <th scope="row">{{ t.classes[r.key] || r.key }}</th>
            <td>
              <span class="whatif-bar ghost" aria-hidden="true"><span :style="{ transform: `scaleX(${r.stored / total})` }"></span></span>
              <span class="num whatif-stored" v-trace="trace">{{ num(r.stored) }} · {{ pct(r.stored / total) }}</span>
            </td>
            <td>
              <span class="whatif-bar" aria-hidden="true"><span :style="{ transform: `scaleX(${r.sim / total})` }"></span></span>
              <span class="num whatif-sim-n" :data-value="r.sim" v-trace="trace">{{ num(shown[r.key] ?? r.sim) }} · {{ pct(r.sim / total) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="data.no_confidence" class="hint num">{{ fill(T.noConfidence, { n: num(data.no_confidence) }) }}</p>
    </template>
    <div v-else class="sheet-loading" aria-hidden="true"><span></span><span></span></div>
  </section>
</template>
