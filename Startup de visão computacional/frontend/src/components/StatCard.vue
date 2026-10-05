<script setup>
import { computed, nextTick, provide, ref, shallowRef } from "vue";
import Walkthrough from "./Walkthrough.vue";
import { num } from "../format.js";
import { errorText, fill, t } from "../strings.js";

const props = defineProps({
  stat: { type: String, required: true },
  title: { type: String, required: true },
  subtitle: { type: String, required: true },
  result: { type: Object, default: null },
  n: { type: Number, default: null },
  unit: { type: String, default: "" },
  span: { type: String, default: "full" },
  shape: { type: String, default: "bars" },
  badges: { type: Array, default: () => [] },
  steps: { type: Array, default: () => [] },
  emptyText: { type: String, default: "" },
  refreshing: { type: Boolean, default: false },
});

const card = ref(null);
const howBtn = ref(null);
const touring = ref(false);
const boxes = shallowRef([]);

provide("registerChart", (box) => {
  boxes.value = [...boxes.value, box];
  return () => (boxes.value = boxes.value.filter((b) => b !== box));
});

const state = computed(() => {
  if (!props.result) return "loading";
  if (props.result.error) return "error";
  return props.result.data.status;
});

const allBadges = computed(() => {
  if (state.value === "loading" || state.value === "error") return [];
  const d = props.result.data;
  return [
    { text: fill(t.badges.n, { n: num(props.n ?? d.n) }), cls: "n-badge", title: props.unit },
    ...(d.demo ? [{ text: t.badges.demo, tone: "demo", cls: "demo-tag", title: t.app.demoBadgeHint }] : []),
    ...(state.value === "ok" ? props.badges : []),
  ];
});

const empty = computed(() => {
  if (state.value === "error") return { title: t.empty.errorTitle, detail: errorText(props.result.error) };
  if (state.value === "no_data") return { title: t.empty.noDataTitle, detail: t.empty.noDataDetail };
  return { title: t.empty.insufficientTitle, detail: props.emptyText };
});

function closeTour() {
  touring.value = false;
  nextTick(() => howBtn.value?.focus());
}
</script>

<template>
  <article ref="card" class="card" :class="[`span-${span}`, { refreshing }]" :data-stat="stat" :aria-busy="state === 'loading' || refreshing">
    <span class="refresh-bar" aria-hidden="true"></span>
    <header class="card-head">
      <div>
        <h2>{{ title }}</h2>
        <p class="subtitle">{{ subtitle }}</p>
      </div>
      <button ref="howBtn" class="how-btn" type="button" :disabled="state !== 'ok' || !steps.length" :aria-expanded="touring" @click="touring = true">
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9" /><path d="M10 9.5a2.2 2.2 0 1 1 3 2c-.7.3-1 .8-1 1.5M12 16.5h.01" /></svg>
        <span>{{ t.tour.how }}</span>
      </button>
    </header>
    <div v-if="allBadges.length" class="badges">
      <span v-for="b in allBadges" :key="b.text" class="badge" :class="[b.tone, b.cls]" :title="b.title">{{ b.text }}</span>
    </div>
    <div v-if="state === 'loading'" class="skeleton" :class="`sk-${shape}`" :aria-label="t.dashboard.loading">
      <span v-for="i in 12" :key="i"></span>
    </div>
    <div v-else-if="state !== 'ok'" class="chart-frame" role="img" tabindex="0" :aria-label="`${empty.title}. ${empty.detail}`">
      <div class="chart-area empty-area" :style="{ height: '220px' }">
        <div class="chart-empty" role="status">
          <svg width="40" height="40" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 19V5M4 19h16" />
            <path d="M8 15l3-3 2 2 4-5" stroke-dasharray="2 2.5" />
          </svg>
          <strong>{{ empty.title }}</strong>
          <span>{{ empty.detail }}</span>
        </div>
      </div>
    </div>
    <slot v-else :data="result.data" />
    <Walkthrough v-if="touring" :steps="steps" :boxes="boxes" :card="card" @close="closeTour" />
  </article>
</template>
