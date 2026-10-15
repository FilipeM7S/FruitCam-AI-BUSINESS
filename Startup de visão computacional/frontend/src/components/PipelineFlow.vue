<script setup>
import "../control.css";
import { onBeforeUnmount, onMounted, ref } from "vue";
import { reducedMotion } from "../media.js";
import { fill, t } from "../strings.js";

const F = t.flow;
const ICONS = [
  "M4 8h3l2-3h6l2 3h3v11H4zM12 10a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z",
  "M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4M9 12h6M12 9v6",
  "M7 7h10v10H7zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4",
  "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3Zm0 0v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  "M3 20h18M6 20v-7M11 20V5M16 20v-10M21 20v-4",
  "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6",
];

const root = ref(null);
const current = ref(-1);
const done = ref(false);
let running = [];
let seen = null;

function stop() {
  running.forEach((a) => a.cancel());
  running = [];
}

function play() {
  stop();
  if (reducedMotion() || !root.value?.animate) {
    current.value = F.steps.length - 1;
    done.value = true;
    return;
  }
  done.value = false;
  current.value = -1;
  const nodes = [...root.value.querySelectorAll(".flow-step")];
  nodes.forEach((node, i) => {
    const delay = i * 560;
    const a = node.animate([{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "none" }], { duration: 420, delay, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)", fill: "backwards" });
    a.onfinish = () => {
      current.value = Math.max(current.value, i);
      if (i === nodes.length - 1) done.value = true;
    };
    running.push(a);
    const icon = node.querySelector(".flow-icon");
    running.push(icon.animate([{ transform: "scale(0.4) rotate(-20deg)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 480, delay: delay + 80, easing: "cubic-bezier(0.2, 0.8, 0.2, 1.2)", fill: "backwards" }));
    const link = node.querySelector(".flow-link span");
    if (link) running.push(link.animate([{ transform: "scale(0)" }, { transform: "scale(1)" }], { duration: 300, delay: delay + 360, easing: "ease-out", fill: "backwards" }));
  });
}

onMounted(() => {
  if (reducedMotion() || !("IntersectionObserver" in window)) return play();
  let started = false;
  seen = new IntersectionObserver(([e]) => {
    if (e.isIntersecting && !started) {
      started = true;
      play();
    } else running.forEach((a) => (e.isIntersecting ? a.playState === "paused" && a.play() : a.playState === "running" && a.pause()));
  }, { threshold: 0.25 });
  seen.observe(root.value);
});

onBeforeUnmount(() => {
  seen?.disconnect();
  stop();
});
</script>

<template>
  <figure ref="root" class="flow paper" :data-state="done ? 'done' : 'playing'" :aria-label="F.label">
    <ol class="flow-steps">
      <li v-for="(s, i) in F.steps" :key="s.title" class="flow-step" :class="{ ai: s.ai, lit: i <= current }">
        <svg class="flow-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path :d="ICONS[i]" /></svg>
        <span class="flow-num num" aria-hidden="true">{{ String(i + 1).padStart(2, "0") }}</span>
        <strong>{{ s.title }}</strong>
        <span class="flow-text">{{ s.text }}</span>
        <span class="flow-kind chip" :data-state="s.ai ? 'ia' : 'off'">{{ s.ai ? t.pipeline.ai : F.code }}</span>
        <span v-if="i < F.steps.length - 1" class="flow-link" aria-hidden="true"><span></span></span>
      </li>
    </ol>
    <figcaption class="flow-status">
      <span aria-live="polite">{{ current >= 0 && !done ? fill(F.status, { i: current + 1, n: F.steps.length, title: F.steps[current].title }) : F.done }}</span>
      <button type="button" class="btn btn-secondary btn-sm" @click="play">{{ F.replay }}</button>
    </figcaption>
  </figure>
</template>
