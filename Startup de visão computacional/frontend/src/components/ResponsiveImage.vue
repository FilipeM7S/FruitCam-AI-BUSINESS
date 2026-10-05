<script setup>
import { computed } from "vue";
import { mediaItem, srcset, url } from "../media.js";
import { t } from "../strings.js";

const props = defineProps({
  id: { type: String, required: true },
  sizes: { type: String, default: "100vw" },
  eager: { type: Boolean, default: false },
  caption: { type: Boolean, default: true },
  cover: { type: Boolean, default: false },
});

const item = computed(() => mediaItem(props.id));
</script>

<template>
  <figure class="media" :class="{ cover }" :data-media="id">
    <picture>
      <source type="image/avif" :srcset="srcset(item, 'avif')" :sizes="sizes" />
      <source type="image/webp" :srcset="srcset(item, 'webp')" :sizes="sizes" />
      <img
        :src="url(item.fallback)"
        :srcset="srcset(item, 'jpeg')"
        :sizes="sizes"
        :width="item.width"
        :height="item.height"
        :alt="item.alt"
        :loading="eager ? 'eager' : 'lazy'"
        :fetchpriority="eager ? 'high' : 'auto'"
        decoding="async"
      />
    </picture>
    <figcaption v-if="caption" class="media-credit">
      <span v-if="item.illustrative" class="illustrative">{{ t.media.illustrative }}</span>
      <RouterLink :to="{ path: '/creditos', hash: `#${item.asset}` }">{{ item.credit }}</RouterLink>
    </figcaption>
  </figure>
</template>
