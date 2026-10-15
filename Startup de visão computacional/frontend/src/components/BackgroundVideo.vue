<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { constrainedData, mediaItem, motion, reducedMotion, url } from "../media.js";
import { t } from "../strings.js";
import ResponsiveImage from "./ResponsiveImage.vue";

const props = defineProps({
  id: { type: String, required: true },
  shade: { type: String, default: "strong" },
});

const item = computed(() => mediaItem(props.id));
const still = computed(() => reducedMotion() || constrainedData());
const box = ref(null);
const video = ref(null);
const paused = ref(false);
let observer = null;
let visible = false;

function run() {
  if (!video.value) return;
  if (visible && !paused.value) video.value.play().catch(() => {});
  else video.value.pause();
}

function start() {
  if (still.value || !video.value) return;
  video.value.muted = true;
  if (!("IntersectionObserver" in window)) {
    visible = true;
    return run();
  }
  observer?.disconnect();
  observer = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    run();
  }, { threshold: 0.05 });
  observer.observe(box.value);
}

function toggle() {
  paused.value = !paused.value;
  run();
}

onMounted(start);
watch(() => motion.reduced, async () => {
  observer?.disconnect();
  await nextTick();
  start();
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<template>
  <div ref="box" class="bg-media" :class="`shade-${shade}`" :data-bg="id" :data-mode="still ? 'poster' : 'video'">
    <div class="bg-layer" aria-hidden="true">
      <ResponsiveImage v-if="still" :id="item.poster" :caption="false" cover eager sizes="100vw" />
      <video v-else ref="video" muted loop playsinline preload="none" disablepictureinpicture :poster="url(item.posterSrc)" :width="item.width" :height="item.height">
        <source v-for="s in item.sources" :key="s.src" :src="url(s.src)" :type="s.type" />
      </video>
      <span class="bg-shade"></span>
    </div>
    <button v-if="!still" class="bg-toggle icon-btn" type="button" :aria-pressed="paused" :aria-label="paused ? t.media.playBackground : t.media.pauseBackground" :title="paused ? t.media.playBackground : t.media.pauseBackground" @click="toggle">
      <svg v-if="paused" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
      <svg v-else width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M7 5h4v14H7zM13 5h4v14h-4z" /></svg>
    </button>
  </div>
</template>
