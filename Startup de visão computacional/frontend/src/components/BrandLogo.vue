<script setup>
import { computed } from "vue";
import { logoAsset, minHeight, theme, url } from "../media.js";
import { t } from "../strings.js";

const props = defineProps({
  kind: { type: String, default: "lockup" },
  on: { type: String, default: "auto" },
  height: { type: Number, default: 40 },
  reveal: { type: Boolean, default: false },
});

const surface = computed(() => (props.on === "auto" ? (theme.dark ? "dark" : "light") : props.on));
const asset = computed(() => logoAsset(props.kind, surface.value));
const h = computed(() => Math.max(props.height, minHeight(props.kind)));
const w = computed(() => Math.round((h.value * asset.value.width) / asset.value.height));
const src = computed(() => (asset.value.renditions || []).find((r) => r.height >= 2 * h.value)?.src || asset.value.src);
</script>

<template>
  <img
    class="brand-logo"
    :class="{ 'logo-reveal': reveal }"
    :src="url(src)"
    :width="w"
    :height="h"
    :alt="t.brand.alt"
    :data-variant="kind === 'icon' ? 'icon' : `on-${surface}`"
    decoding="async"
  />
</template>
