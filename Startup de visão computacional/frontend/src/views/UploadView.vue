<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { api } from "../api.js";
import { confidence, num } from "../format.js";
import { errorText, t } from "../strings.js";
import ResponsiveImage from "../components/ResponsiveImage.vue";
import { credits } from "../media.js";

const TYPES = ["image/jpeg", "image/png", "image/webp"];
const FRUITS = Object.keys(t.fruits);
const BAD = ["guia-varias", "guia-longe", "guia-escuro"];
const fruitCredits = credits(FRUITS.map((f) => `fruta-${f}`));
const guideCredits = credits(["guia-bom", ...BAD]);
const heroCredit = credits(["hero-caju"])[0].credit;

const sector = ref("");
const fruit = ref("");
const file = ref(null);
const preview = ref("");
const dragging = ref(false);
const busy = ref(false);
const message = ref("");
const result = ref(null);
const sectors = ref([]);
const picker = ref(null);
const camera = ref(null);

const ready = computed(() => file.value && sector.value.trim() && fruit.value && !busy.value);
const det = computed(() => result.value?.detections[0]);
const TONE = { boa: "good", nao_podre: "good", baixa_qualidade: "poor", podre: "rotten" };
const tone = computed(() => (det.value?.needs_review ? "review" : TONE[det.value?.label] || "review"));
const probs = computed(() => (result.value ? result.value.classes.map((c) => ({ c, p: det.value.probs[c] })) : []));

onMounted(async () => {
  try {
    sectors.value = (await api("/api/sectors")).sectors;
  } catch {
    sectors.value = [];
  }
});
onBeforeUnmount(() => preview.value && URL.revokeObjectURL(preview.value));

function choose(f) {
  if (!f) return;
  message.value = "";
  result.value = null;
  if (!TYPES.includes(f.type)) {
    message.value = t.upload.badType;
    return;
  }
  if (preview.value) URL.revokeObjectURL(preview.value);
  file.value = f;
  preview.value = URL.createObjectURL(f);
}

function onDrop(e) {
  dragging.value = false;
  choose(e.dataTransfer?.files?.[0]);
}

async function submit() {
  if (!ready.value) {
    message.value = t.upload.missing;
    return;
  }
  busy.value = true;
  message.value = "";
  result.value = null;
  const form = new FormData();
  form.append("image", file.value);
  form.append("sector", sector.value);
  form.append("fruit_type", fruit.value);
  try {
    result.value = await api("/api/analyze", { method: "POST", body: form });
    if (!sectors.value.includes(result.value.event.sector)) sectors.value = [...sectors.value, result.value.event.sector].sort();
  } catch (err) {
    message.value = errorText(err);
  } finally {
    busy.value = false;
  }
}

function reset() {
  result.value = null;
  message.value = "";
  file.value = null;
  if (preview.value) URL.revokeObjectURL(preview.value);
  preview.value = "";
}
</script>

<template>
  <section class="page">
    <header class="page-head page-banner">
      <ResponsiveImage id="hero-caju" cover :caption="false" sizes="(min-width: 1160px) 1096px, 100vw" />
      <div class="banner-text page-head-text">
        <h1>{{ t.upload.title }}</h1>
        <p class="lead">{{ t.upload.subtitle }}</p>
        <p class="bg-credit">
          <span class="illustrative">{{ t.media.illustrative }}</span>
          <RouterLink :to="{ path: '/creditos', hash: '#caju-arvore' }">{{ heroCredit }}</RouterLink>
        </p>
      </div>
    </header>

    <div class="analyze-grid">
      <form class="panel stack" @submit.prevent="submit" novalidate>
        <label class="field">
          <span>{{ t.upload.sector }}</span>
          <input v-model="sector" list="sector-list" maxlength="50" :placeholder="t.upload.sectorPlaceholder" autocomplete="off" required />
          <datalist id="sector-list">
            <option v-for="s in sectors" :key="s" :value="s" />
          </datalist>
        </label>

        <fieldset class="field">
          <legend>{{ t.upload.fruit }}</legend>
          <div class="fruit-cards">
            <label v-for="f in FRUITS" :key="f" class="fruit-card" :class="{ active: fruit === f, untrained: f !== 'caju' }">
              <input v-model="fruit" type="radio" name="fruit" :value="f" />
              <ResponsiveImage :id="`fruta-${f}`" :caption="false" sizes="88px" />
              <span class="fruit-name">{{ t.fruits[f] }}</span>
              <span class="fruit-status">{{ t.fruitStatus[f] }}</span>
            </label>
          </div>
          <p class="group-credit">
            <span class="illustrative">{{ t.media.illustrative }}</span>
            <RouterLink v-for="c in fruitCredits" :key="c.asset" :to="{ path: '/creditos', hash: `#${c.asset}` }">{{ c.credit }}</RouterLink>
          </p>
        </fieldset>

        <figure v-if="result" class="annotated">
          <img :src="preview" :alt="t.upload.previewAlt" />
          <svg :viewBox="`0 0 ${result.image.width} ${result.image.height}`" preserveAspectRatio="none" aria-hidden="true">
            <rect
              v-for="(d, i) in result.detections"
              :key="i"
              class="box"
              :class="tone"
              :style="{ animationDelay: `${0.15 + i * 0.18}s` }"
              :x="d.box[0]"
              :y="d.box[1]"
              :width="d.box[2] - d.box[0] + 1"
              :height="d.box[3] - d.box[1] + 1"
              fill="none"
              stroke-width="3"
              vector-effect="non-scaling-stroke"
              rx="4"
            />
          </svg>
          <span v-for="(d, i) in result.detections" :key="i" class="box-tag" :class="tone" :style="{ left: `${(100 * d.box[0]) / result.image.width}%`, top: `${(100 * d.box[1]) / result.image.height}%`, animationDelay: `${0.45 + i * 0.18}s` }">
            {{ t.classes[d.label] || d.label }} · {{ confidence(d.confidence) }}
          </span>
        </figure>
        <div
          class="dropzone"
          :class="{ dragging, filled: preview }"
          role="button"
          tabindex="0"
          :aria-label="`${t.upload.dropTitle}. ${t.upload.dropHint}`"
          @click="picker.click()"
          @keydown.enter.prevent="picker.click()"
          @keydown.space.prevent="picker.click()"
          @dragenter.prevent="dragging = true"
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop.prevent="onDrop"
        >
          <div v-if="preview && !result" class="dropzone-preview" :class="{ scanning: busy }">
            <img :src="preview" :alt="t.upload.previewAlt" />
            <span v-if="busy" class="scan" aria-hidden="true"><span class="scan-line"></span></span>
          </div>
          <div v-else-if="!preview" class="dropzone-empty">
            <svg width="40" height="40" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
              <path d="M12 4v11" />
              <path d="m7 9 5-5 5 5" />
            </svg>
            <strong>{{ dragging ? t.upload.dropActive : t.upload.dropTitle }}</strong>
            <span class="muted small">{{ t.upload.dropHint }}</span>
          </div>
          <div v-else class="dropzone-empty compact">
            <strong>{{ t.upload.change }}</strong>
          </div>
        </div>
        <input ref="picker" class="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" tabindex="-1" :aria-label="t.upload.dropTitle" @change="choose($event.target.files[0]); $event.target.value = ''" />
        <input ref="camera" class="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" tabindex="-1" :aria-label="t.upload.camera" @change="choose($event.target.files[0]); $event.target.value = ''" />

        <div class="row">
          <button class="btn btn-secondary" type="button" @click="camera.click()">
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
              <circle cx="12" cy="13" r="3.5" />
            </svg>
            {{ t.upload.camera }}
          </button>
          <button class="btn btn-primary grow" type="submit" :disabled="busy">
            <span v-if="busy" class="spinner" aria-hidden="true"></span>
            {{ busy ? t.upload.submitting : t.upload.submit }}
          </button>
        </div>
        <p v-if="message" class="notice error" role="alert">{{ message }}</p>
      </form>

      <section class="panel result" aria-live="polite" :aria-busy="busy">
        <h2 class="visually-hidden">{{ t.upload.result }}</h2>
        <div v-if="busy" class="result-loading">
          <div class="sk-result" aria-hidden="true">
            <span class="sk-photo"></span>
            <span class="sk-verdict"></span>
            <span class="sk-fact"></span>
            <span class="sk-fact short"></span>
          </div>
          <p>{{ t.upload.scanning }}</p>
        </div>
        <template v-else-if="result">
          <div class="verdict pop" :class="tone">
            <span class="verdict-icon" aria-hidden="true">
              <svg v-if="tone === 'good'" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 5 5 9-10" /></svg>
              <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 7v6M12 17h.01" /><circle cx="12" cy="12" r="9" /></svg>
            </span>
            <div>
              <p class="verdict-label">{{ t.classes[det.label] || det.label }}</p>
              <p class="small">{{ t.fruits[result.event.fruit_type] }} · {{ result.event.sector }}</p>
            </div>
          </div>
          <p v-if="det.needs_review" class="notice review-note" role="status">{{ t.upload.review }}</p>

          <div class="probs">
            <p class="probs-title">{{ t.upload.probs }}</p>
            <div v-for="row in probs" :key="row.c" class="prob-row" :class="TONE[row.c]">
              <span class="prob-name">{{ t.classes[row.c] || row.c }}</span>
              <span class="prob-bar" aria-hidden="true"><span :style="{ transform: `scaleX(${row.p})` }"></span></span>
              <span class="prob-value">{{ confidence(row.p) }}</span>
            </div>
          </div>

          <dl class="facts">
            <div>
              <dt>{{ t.upload.confidence }}</dt>
              <dd>
                {{ confidence(det.confidence) }}
                <span class="meter" aria-hidden="true"><span :style="{ transform: `scaleX(${det.confidence})` }"></span></span>
              </dd>
            </div>
            <div>
              <dt>{{ t.upload.time }}</dt>
              <dd>{{ num(result.inference_ms) }} ms</dd>
            </div>
            <div>
              <dt>{{ t.upload.model }}</dt>
              <dd>{{ result.model_version }}</dd>
            </div>
          </dl>
          <p class="hint">{{ t.upload.confidenceNote }}</p>
          <p class="hint">{{ t.upload.oneFruit }}</p>
          <p class="hint">{{ t.upload.saved }} #{{ result.event.id }}</p>
          <button class="btn btn-secondary btn-block" type="button" @click="reset">{{ t.upload.again }}</button>
        </template>
        <div v-else class="guide">
          <h2 class="guide-title">{{ t.guide.title }}</h2>
          <div class="guide-good">
            <ResponsiveImage id="guia-bom" :caption="false" sizes="(min-width: 960px) 240px, 40vw" />
            <div>
              <p class="guide-tag good"><span aria-hidden="true">✓</span> {{ t.guide.good }}</p>
              <ul class="guide-tips">
                <li v-for="tip in t.guide.tips" :key="tip">{{ tip }}</li>
              </ul>
            </div>
          </div>
          <p class="guide-tag bad"><span aria-hidden="true">✕</span> {{ t.guide.bad }}</p>
          <ul class="guide-bad">
            <li v-for="id in BAD" :key="id">
              <ResponsiveImage :id="id" :caption="false" sizes="(min-width: 960px) 150px, 30vw" />
              <span>{{ t.guide.badges[id] }}</span>
            </li>
          </ul>
          <p class="group-credit">
            <span class="illustrative">{{ t.media.illustrative }}</span>
            <RouterLink v-for="c in guideCredits" :key="c.asset" :to="{ path: '/creditos', hash: `#${c.asset}` }">{{ c.credit }}</RouterLink>
          </p>
          <p class="hint">{{ t.guide.note }}</p>
          <p class="hint">{{ t.upload.oneFruit }}</p>
        </div>
      </section>
    </div>
  </section>
</template>
