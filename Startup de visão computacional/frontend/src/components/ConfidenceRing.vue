<script setup>
import "../control.css";
import { computed, onMounted, ref, watch } from "vue";
import { confidence } from "../format.js";
import { reducedMotion } from "../media.js";

const props = defineProps({
  value: { type: Number, required: true },
  size: { type: Number, default: 72 },
  tone: { type: String, default: "active" },
  label: { type: String, default: "" },
});

const right = ref(null);
const left = ref(null);
const a = computed(() => Math.min(1, Math.max(0, props.value)));
const turnRight = computed(() => `rotate(${Math.min(a.value, 0.5) * 360}deg)`);
const turnLeft = computed(() => `rotate(${Math.max(a.value - 0.5, 0) * 360}deg)`);
const s = computed(() => props.size);
const w = computed(() => Math.max(5, Math.round(props.size / 11)));
const r = computed(() => (s.value - w.value) / 2);
const leftArc = computed(() => `M ${s.value / 2} ${w.value / 2} A ${r.value} ${r.value} 0 0 0 ${s.value / 2} ${s.value - w.value / 2}`);
const rightArc = computed(() => `M ${s.value / 2} ${w.value / 2} A ${r.value} ${r.value} 0 0 1 ${s.value / 2} ${s.value - w.value / 2}`);

function play() {
  if (reducedMotion() || !right.value?.animate) return;
  const first = Math.min(a.value, 0.5) / Math.max(a.value, 0.001);
  const total = 900;
  right.value.animate([{ transform: "rotate(0deg)" }, { transform: turnRight.value }], { duration: total * first, easing: a.value > 0.5 ? "ease-in" : "cubic-bezier(0.2, 0.7, 0.2, 1)", fill: "backwards" });
  if (a.value > 0.5) left.value.animate([{ transform: "rotate(0deg)" }, { transform: turnLeft.value }], { duration: total * (1 - first), delay: total * first, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)", fill: "backwards" });
}

onMounted(play);
watch(() => props.value, play);
</script>

<template>
  <span class="ring" :class="`ring-${tone}`" :style="{ width: `${s}px`, height: `${s}px` }" role="img" :aria-label="label || confidence(a)">
    <svg class="ring-track" :viewBox="`0 0 ${s} ${s}`" aria-hidden="true"><circle :cx="s / 2" :cy="s / 2" :r="r" fill="none" :stroke-width="w" /></svg>
    <span class="ring-half ring-right" aria-hidden="true">
      <svg ref="right" :viewBox="`0 0 ${s} ${s}`" :style="{ transform: turnRight }"><path :d="leftArc" fill="none" :stroke-width="w" /></svg>
    </span>
    <span class="ring-half ring-left" aria-hidden="true">
      <svg ref="left" :viewBox="`0 0 ${s} ${s}`" :style="{ transform: turnLeft }"><path :d="rightArc" fill="none" :stroke-width="w" /></svg>
    </span>
    <span class="ring-value num" aria-hidden="true"><slot>{{ confidence(a) }}</slot></span>
  </span>
</template>
