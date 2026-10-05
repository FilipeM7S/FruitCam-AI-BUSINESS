<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from "vue";
import { Chart, reduced, stagger } from "../charts.js";

const props = defineProps({
  spec: { type: Object, default: null },
  height: { type: Number, default: 260 },
  empty: { type: Object, default: null },
  caption: { type: String, default: "" },
  badges: { type: Array, default: () => [] },
});

const frame = ref(null);
const canvas = ref(null);
const overlays = shallowRef([]);
const counters = reactive({});
const shown = ref(false);
const first = ref(true);
const motion = ref(!reduced());
const register = inject("registerChart", null);
let chart = null;
let visible = false;
let observer = null;
let timer = 0;
let raf = 0;
let dimRaf = 0;
let unregister = null;

const label = computed(() => {
  const text = props.empty ? `${props.empty.title}. ${props.empty.detail || ""}` : props.spec?.finding || "";
  return props.caption && !text.startsWith(props.caption) ? `${props.caption}: ${text}` : text;
});

function entry(n) {
  let done = false;
  const step = Math.min(28, 650 / Math.max(n, 1));
  return {
    duration: 700,
    easing: "easeOutCubic",
    onComplete: () => (done = true),
    delay: (c) => (!done && c.type === "data" && c.mode === "default" ? c.dataIndex * step + c.datasetIndex * 90 : 0),
  };
}

function prepare(spec, initial) {
  const cfg = spec.config;
  const o = (cfg.options = cfg.options || {});
  const m = !reduced();
  motion.value = m;
  const longest = Math.max(1, ...cfg.data.datasets.map((d) => d.data.length));
  o.animation = !m ? false : initial ? entry(longest) : { duration: 650, easing: "easeInOutCubic" };
  o.plugins = o.plugins || {};
  o.plugins.tooltip = { ...(o.plugins.tooltip || {}), animation: m ? { duration: 160 } : false };
  if (spec.dim !== false && cfg.data.datasets.length > 1) {
    o.onHover = (_, els) => dimTo(els.length ? els[0].datasetIndex : null);
    o.plugins.legend = { ...(o.plugins.legend || {}), onHover: (_, item) => dimTo(item.datasetIndex), onLeave: () => dimTo(null) };
  }
  o.onResize = () => schedule();
  return cfg;
}

function dimTo(index) {
  const d = chart?.$dim;
  if (!d) return;
  const target = index == null ? 0 : 1;
  if (index != null) d.index = index;
  if (d.amount === target && (index == null || d.index === index)) return chart.draw();
  cancelAnimationFrame(dimRaf);
  if (reduced()) {
    d.amount = target;
    if (!target) d.index = null;
    return chart.draw();
  }
  const from = d.amount;
  const t0 = performance.now();
  const tick = (now) => {
    const k = Math.min(1, (now - t0) / 180);
    d.amount = from + (target - from) * k;
    chart?.draw();
    if (k < 1) dimRaf = requestAnimationFrame(tick);
    else if (!target) d.index = null;
  };
  dimRaf = requestAnimationFrame(tick);
}

function countTo(o) {
  const from = counters[o.key] ?? 0;
  if (reduced() || from === o.value) {
    counters[o.key] = o.value;
    return;
  }
  const t0 = performance.now();
  const tick = (now) => {
    const k = Math.min(1, (now - t0) / 900);
    counters[o.key] = from + (o.value - from) * (1 - Math.pow(1 - k, 3));
    if (k < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function schedule() {
  cancelAnimationFrame(raf);
  raf = requestAnimationFrame(() => {
    if (!chart || !props.spec?.overlays) {
      overlays.value = [];
      return;
    }
    const list = props.spec.overlays(chart).filter(Boolean);
    list.filter((o) => o.kind === "counter").forEach(countTo);
    overlays.value = list;
    shown.value = true;
  });
}

function create() {
  if (chart || !props.spec || !canvas.value) return;
  first.value = true;
  chart = new Chart(canvas.value, prepare(props.spec, true));
  chart.$dim = { index: null, amount: 0 };
  schedule();
}

function start() {
  visible = true;
  timer = setTimeout(create, reduced() ? 0 : stagger());
}

function destroy() {
  chart?.destroy();
  chart = null;
  overlays.value = [];
  shown.value = false;
}

function morph(cfg) {
  const ds = chart.data.datasets;
  cfg.data.datasets.forEach((d, i) => {
    if (!ds[i]) return ds.push(d);
    for (const k of Object.keys(ds[i])) if (!(k in d)) delete ds[i][k];
    Object.assign(ds[i], d);
  });
  ds.splice(cfg.data.datasets.length);
  chart.data.labels = cfg.data.labels;
  chart.options = cfg.options;
}

watch(
  () => props.spec,
  (spec) => {
    if (!spec) return destroy();
    if (!chart) return visible && create();
    if (chart.config.type !== spec.config.type) {
      destroy();
      return requestAnimationFrame(create);
    }
    first.value = false;
    morph(prepare(spec, false));
    chart.update();
    schedule();
  },
);

onMounted(() => {
  unregister = register?.({ chart: () => chart, canvas: () => canvas.value, frame: () => frame.value });
  if (!("IntersectionObserver" in window)) return start();
  observer = new IntersectionObserver((entries) => {
    if (!entries.some((e) => e.isIntersecting)) return;
    observer.disconnect();
    start();
  }, { rootMargin: "120px" });
  observer.observe(frame.value);
});

onBeforeUnmount(() => {
  observer?.disconnect();
  clearTimeout(timer);
  cancelAnimationFrame(raf);
  cancelAnimationFrame(dimRaf);
  destroy();
  unregister?.();
});

function shift(o) {
  const w = canvas.value?.clientWidth || 0;
  const horizontal = { above: "-50%", below: "-50%", left: "-100%", right: "0%", "above-left": "-100%", "above-right": "0%", "below-left": "-100%", "below-right": "0%" }[o.place] || "-50%";
  const vertical = { above: "-100%", below: "0%", left: "-50%", right: "-50%", "above-left": "-100%", "above-right": "-100%", "below-left": "0%", "below-right": "0%" }[o.place] || "-50%";
  const edge = o.place === "above" || o.place === "below" ? (o.x < 56 ? "0%" : o.x > w - 56 ? "-100%" : horizontal) : horizontal;
  return `translate3d(${Math.round(o.x)}px, ${Math.round(o.y)}px, 0) translate(${edge}, ${vertical})`;
}

defineExpose({ chart: () => chart });
</script>

<template>
  <div ref="frame" class="chart-frame" :class="{ shown, first }" :data-motion="motion ? 'on' : 'off'" tabindex="0" role="img" :aria-label="label">
    <div v-if="caption || badges.length" class="frame-head">
      <h3 v-if="caption">{{ caption }}</h3>
      <span v-for="b in badges" :key="b.text" class="badge" :class="[b.tone, b.cls]" :title="b.title">{{ b.text }}</span>
    </div>
    <div class="chart-area" :class="{ dimmed: empty }" :style="{ height: `${height}px` }">
      <canvas v-if="spec" ref="canvas" aria-hidden="true"></canvas>
      <div class="overlays" aria-hidden="true">
        <span v-for="o in overlays" :key="o.key" class="overlay" :class="[`o-${o.kind}`, `p-${o.place}`, o.tone]" :style="{ transform: shift(o) }">
          <strong v-if="o.kind === 'counter'">{{ o.format(counters[o.key] ?? 0) }}</strong>
          <span v-if="o.kind === 'counter'" class="o-label">{{ o.text }}</span>
          <template v-else>
            <strong>{{ o.text }}</strong>
            <small v-if="o.sub">{{ o.sub }}</small>
          </template>
        </span>
      </div>
      <div v-if="empty" class="chart-empty" role="status">
        <svg width="40" height="40" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 19V5M4 19h16" />
          <path d="M8 15l3-3 2 2 4-5" stroke-dasharray="2 2.5" />
        </svg>
        <strong>{{ empty.title }}</strong>
        <span v-if="empty.detail">{{ empty.detail }}</span>
      </div>
    </div>
  </div>
</template>
