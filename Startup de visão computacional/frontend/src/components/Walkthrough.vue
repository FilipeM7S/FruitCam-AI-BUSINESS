<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { elRect, reduced } from "../charts.js";
import { fill, t } from "../strings.js";

const props = defineProps({
  steps: { type: Array, required: true },
  boxes: { type: Array, required: true },
  card: { type: Object, required: true },
});
const emit = defineEmits(["close"]);

const index = ref(0);
const rect = ref(null);
const size = ref({ w: 0, h: 0 });
const root = ref(null);
const auto = ref(!reduced());
let timer = 0;

const step = computed(() => props.steps[index.value]);
const last = computed(() => index.value === props.steps.length - 1);
const bubble = computed(() => {
  const r = rect.value;
  if (!r) return { transform: "translate(16px, 16px)" };
  const width = Math.min(280, size.value.w - 24);
  const x = Math.max(12, Math.min(r.left, size.value.w - width - 12));
  const below = r.top + r.height + 96 < size.value.h - 56;
  const y = below ? r.top + r.height + 10 : Math.max(8, r.top - 10);
  return { width: `${width}px`, transform: `translate(${x}px, ${y}px) translateY(${below ? "0" : "-100%"})` };
});

function pad(r) {
  return { left: r.left - 6, top: r.top - 6, width: r.right - r.left + 12, height: r.bottom - r.top + 12 };
}

function resolve(target) {
  const card = props.card.getBoundingClientRect();
  const rel = (b) => ({ left: b.left - card.left, top: b.top - card.top, right: b.right - card.left, bottom: b.bottom - card.top });
  if (target.selector) {
    const el = props.card.querySelector(target.selector);
    if (el) return pad(rel(el.getBoundingClientRect()));
  }
  const box = props.boxes[target.chart || 0] || props.boxes[0];
  const chart = box?.chart();
  const canvas = box?.canvas();
  if (!chart || !canvas) {
    const f = box?.frame();
    return f ? pad(rel(f.getBoundingClientRect())) : null;
  }
  const c = canvas.getBoundingClientRect();
  const a = chart.chartArea;
  const x = chart.scales.x;
  const y = chart.scales.y;
  let r = null;
  if (target.area === "legend" && chart.legend?.width) r = { left: chart.legend.left, top: chart.legend.top, right: chart.legend.right, bottom: chart.legend.bottom };
  else if (target.area === "x" || target.area === "y") r = { left: chart.scales[target.area].left, top: chart.scales[target.area].top, right: chart.scales[target.area].right, bottom: chart.scales[target.area].bottom };
  else if (target.el) r = elRect(chart, ...target.el);
  else if (target.y != null) r = { left: a.left, right: a.right, top: y.getPixelForValue(target.y) - 5, bottom: y.getPixelForValue(target.y) + 5 };
  else if (target.x != null) r = { left: x.getPixelForValue(target.x) - 5, right: x.getPixelForValue(target.x) + 5, top: a.top, bottom: a.bottom };
  else if (target.xRange) r = { left: Math.max(a.left, x.getPixelForValue(target.xRange[0])), right: Math.min(a.right, x.getPixelForValue(target.xRange[1])), top: a.top, bottom: a.bottom };
  else if (target.at) {
    const px = x.getPixelForValue(target.at[0]);
    const [y0, y1] = [y.getPixelForValue(target.at[1]), y.getPixelForValue(target.at[2])];
    r = { left: px - 10, right: px + 10, top: Math.min(y0, y1), bottom: Math.max(y0, y1) };
  }
  r = r || { left: a.left, top: a.top, right: a.right, bottom: a.bottom };
  const ox = c.left - card.left;
  const oy = c.top - card.top;
  return pad({ left: r.left + ox, right: r.right + ox, top: r.top + oy, bottom: r.bottom + oy });
}

function place() {
  const card = props.card.getBoundingClientRect();
  size.value = { w: card.width, h: card.height };
  rect.value = resolve(step.value.target);
}

function go(i, manual = true) {
  if (manual) auto.value = false;
  clearTimeout(timer);
  index.value = Math.max(0, Math.min(props.steps.length - 1, i));
  place();
  if (auto.value && !last.value) timer = setTimeout(() => go(index.value + 1, false), 2800);
}

function key(e) {
  if (e.key === "Escape") emit("close");
  else if (e.key === "ArrowRight") go(index.value + 1);
  else if (e.key === "ArrowLeft") go(index.value - 1);
}

onMounted(() => {
  go(0, false);
  root.value?.focus();
  window.addEventListener("resize", place);
  window.addEventListener("keydown", key);
});
onBeforeUnmount(() => {
  clearTimeout(timer);
  window.removeEventListener("resize", place);
  window.removeEventListener("keydown", key);
});
</script>

<template>
  <div ref="root" class="tour" role="dialog" tabindex="-1" :aria-label="t.tour.label">
    <Transition name="spot">
      <div v-if="rect" :key="index" class="tour-spot" :style="{ transform: `translate(${rect.left}px, ${rect.top}px)`, width: `${rect.width}px`, height: `${rect.height}px` }"></div>
    </Transition>
    <Transition name="bubble">
      <div :key="index" class="tour-bubble" :style="bubble" aria-live="polite">
        <span class="tour-count">{{ fill(t.tour.step, { i: index + 1, n: steps.length }) }}</span>
        <p>{{ step.text }}</p>
        <div class="tour-dots" aria-hidden="true">
          <span v-for="(s, i) in steps" :key="i" :class="{ on: i === index }"></span>
        </div>
      </div>
    </Transition>
    <div class="tour-controls">
      <button type="button" class="btn btn-ghost btn-sm" @click="emit('close')">{{ t.tour.skip }}</button>
      <span class="grow"></span>
      <button type="button" class="btn btn-secondary btn-sm" :disabled="index === 0" @click="go(index - 1)">{{ t.tour.prev }}</button>
      <button v-if="!last" type="button" class="btn btn-primary btn-sm tour-next" @click="go(index + 1)">{{ t.tour.next }}</button>
      <button v-else type="button" class="btn btn-primary btn-sm tour-next" @click="emit('close')">{{ t.tour.done }}</button>
    </div>
  </div>
</template>
