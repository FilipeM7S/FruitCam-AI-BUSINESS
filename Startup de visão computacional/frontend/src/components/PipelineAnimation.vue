<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { reducedMotion } from "../media.js";
import { fill, t } from "../strings.js";

const steps = t.pipeline.steps;
const root = ref(null);
const current = ref(-1);
const done = ref(false);
const armed = ref(!reducedMotion());
let animations = [];
let observer = null;

function reset() {
  animations.forEach((a) => a.cancel());
  animations = [];
}

function play() {
  reset();
  if (reducedMotion()) {
    armed.value = false;
    current.value = steps.length - 1;
    done.value = true;
    return;
  }
  done.value = false;
  current.value = -1;
  const nodes = [...root.value.querySelectorAll(".pipe-node")];
  const links = [...root.value.querySelectorAll(".pipe-link span")];
  nodes.forEach((node, i) => {
    const delay = i * 650;
    const a = node.animate(
      [{ opacity: 0, transform: "translateY(12px) scale(0.96)" }, { opacity: 1, transform: "none" }],
      { duration: 460, delay, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)", fill: "backwards" },
    );
    a.onfinish = () => {
      current.value = Math.max(current.value, i);
      if (i === nodes.length - 1) done.value = true;
    };
    animations.push(a);
    if (links[i]) animations.push(links[i].animate([{ transform: "scale(0)" }, { transform: "scale(1)" }], { duration: 320, delay: delay + 380, easing: "ease-out", fill: "backwards" }));
  });
  armed.value = false;
}

onMounted(() => {
  if (reducedMotion() || !("IntersectionObserver" in window)) return play();
  observer = new IntersectionObserver((entries) => {
    if (!entries.some((e) => e.isIntersecting)) return;
    observer.disconnect();
    play();
  }, { threshold: 0.3 });
  observer.observe(root.value);
});

onBeforeUnmount(() => {
  observer?.disconnect();
  reset();
});
</script>

<template>
  <figure ref="root" class="pipeline paper" :class="{ armed }" :data-state="done ? 'done' : 'playing'">
    <ol class="pipe">
      <template v-for="(s, i) in steps" :key="s.title">
        <li class="pipe-node" :class="{ ai: s.ai, active: i === current && !done }">
          <span class="pipe-num" aria-hidden="true">{{ i + 1 }}</span>
          <strong>{{ s.title }}</strong>
          <span class="pipe-text">{{ s.text }}</span>
          <span class="pipe-kind">{{ s.ai ? t.pipeline.ai : t.pipeline.code }}</span>
        </li>
        <li v-if="i < steps.length - 1" class="pipe-link" aria-hidden="true"><span></span></li>
      </template>
    </ol>
    <figcaption class="pipe-status">
      <span aria-live="polite">{{ current >= 0 && !done ? fill(t.pipeline.status, { i: current + 1, n: steps.length, title: steps[current].title }) : t.pipeline.summary }}</span>
      <button type="button" class="btn btn-secondary btn-sm pipe-replay" @click="play">{{ t.pipeline.replay }}</button>
    </figcaption>
  </figure>
</template>
