<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { constrainedData, mediaItem, reducedMotion, url } from "../media.js";
import { t } from "../strings.js";
import ResponsiveImage from "./ResponsiveImage.vue";

const props = defineProps({ id: { type: String, required: true } });

const item = computed(() => mediaItem(props.id));
const fallback = ref(reducedMotion() || constrainedData());
const playing = ref(false);
const near = ref(false);
const box = ref(null);
const video = ref(null);
let observer = null;
let nearObserver = null;

async function play() {
  try {
    await video.value?.play();
    playing.value = true;
  } catch {
    playing.value = false;
  }
}

function pause() {
  video.value?.pause();
  playing.value = false;
}

async function startManually() {
  fallback.value = false;
  near.value = true;
  await nextTick();
  play();
}

onMounted(() => {
  if (fallback.value) return;
  if (!("IntersectionObserver" in window)) {
    near.value = true;
    return;
  }
  nearObserver = new IntersectionObserver(([entry]) => {
    if (!entry.isIntersecting) return;
    near.value = true;
    nearObserver.disconnect();
  }, { rootMargin: "600px 0px" });
  nearObserver.observe(box.value);
  observer = new IntersectionObserver(([entry]) => (entry.isIntersecting ? play() : pause()), { threshold: 0.35 });
  observer.observe(box.value);
});

onBeforeUnmount(() => {
  observer?.disconnect();
  nearObserver?.disconnect();
});
</script>

<template>
  <figure ref="box" class="video-figure" :data-video="id" :data-mode="fallback ? 'poster' : 'video'">
    <div v-if="fallback" class="video-fallback">
      <ResponsiveImage :id="item.poster" :caption="false" sizes="(min-width: 960px) 880px, 100vw" />
      <button class="btn btn-secondary btn-sm video-start" type="button" @click="startManually">{{ t.media.playVideo }}</button>
    </div>
    <div v-else class="video-frame">
      <video
        ref="video"
        muted
        loop
        playsinline
        preload="none"
        :poster="near ? url(item.posterSrc) : undefined"
        :width="item.width"
        :height="item.height"
        :aria-label="item.alt"
      >
        <source :src="url(item.webm)" type="video/webm" />
        <source :src="url(item.mp4)" type="video/mp4" />
        <track kind="captions" srclang="pt-BR" :label="t.media.captionsLabel" :src="url(item.captions)" default />
      </video>
      <button class="video-toggle" type="button" :aria-pressed="playing" @click="playing ? pause() : play()">
        <span aria-hidden="true">{{ playing ? "❚❚" : "▶" }}</span>
        <span>{{ playing ? t.media.pause : t.media.play }}</span>
      </button>
    </div>
    <figcaption class="video-caption">
      <span class="illustrative synthetic">{{ t.media.syntheticDemo }}</span>
      <span>{{ item.caption }}</span>
      <details class="transcript">
        <summary>{{ t.media.transcript }}</summary>
        <ol>
          <li v-for="line in item.transcript" :key="line">{{ line }}</li>
        </ol>
      </details>
    </figcaption>
  </figure>
</template>
