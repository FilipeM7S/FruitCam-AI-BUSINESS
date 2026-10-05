<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { constrainedData, mediaItem, reducedMotion, url } from "../media.js";
import ResponsiveImage from "./ResponsiveImage.vue";

const props = defineProps({
  id: { type: String, required: true },
  shade: { type: String, default: "strong" },
});

const item = computed(() => mediaItem(props.id));
const still = reducedMotion() || constrainedData();
const box = ref(null);
const video = ref(null);
let observer = null;

onMounted(() => {
  if (still || !video.value) return;
  video.value.muted = true;
  if (!("IntersectionObserver" in window)) {
    video.value.play().catch(() => {});
    return;
  }
  observer = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting) video.value.play().catch(() => {});
    else video.value.pause();
  }, { threshold: 0.05 });
  observer.observe(box.value);
});

onBeforeUnmount(() => observer?.disconnect());
</script>

<template>
  <div ref="box" class="bg-media" :class="`shade-${shade}`" :data-bg="id" :data-mode="still ? 'poster' : 'video'" aria-hidden="true">
    <ResponsiveImage v-if="still" :id="item.poster" :caption="false" cover eager sizes="100vw" />
    <video v-else ref="video" muted loop playsinline preload="none" disablepictureinpicture :poster="url(item.posterSrc)" :width="item.width" :height="item.height">
      <source v-for="s in item.sources" :key="s.src" :src="url(s.src)" :type="s.type" />
    </video>
    <span class="bg-shade"></span>
  </div>
</template>
