<script setup>
import "../control.css";
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api.js";
import { closePanel, openDrill, openEventId, panel, vTrace } from "../control.js";
import { confidence, deformityName, fruitName, num } from "../format.js";
import { reducedMotion } from "../media.js";
import { fill, t } from "../strings.js";
import ConfidenceRing from "./ConfidenceRing.vue";

const LotReplay = defineAsyncComponent(() => import("./LotReplay.vue"));
const T = t.control.inspector;
const ORDER = ["label", "confidence", "deformity_type", "timestamp", "sector", "fruit_type", "lot", "camera", "track_id", "size_mm", "needs_review", "decided_by", "model_version", "source", "user", "id"];
const TONE = { boa: "good", baixa_qualidade: "poor", podre: "rotten" };

const router = useRouter();
const dialog = ref(null);
const crop = ref(null);
const event = ref(null);
const failed = ref(false);
const drill = ref(null);
const back = ref(null);
const line = ref(null);

const fresh = computed(() => panel.extra);
const title = computed(() => {
  if (panel.mode === "replay") return fill(t.control.replay.title, { lot: panel.replay.lot });
  if (panel.mode === "drill") return fill(t.control.drill.title, { what: panel.drill.title });
  return fill(T.title, { id: panel.id });
});
const tone = computed(() => (event.value?.needs_review ? "review" : TONE[event.value?.label] || "review"));

function show(key, value) {
  if (value == null || value === "") return null;
  if (key === "label") return t.classes[value] || value;
  if (key === "confidence") return confidence(value);
  if (key === "deformity_type") return deformityName(value);
  if (key === "timestamp") return new Date(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "medium" });
  if (key === "fruit_type") return fruitName(value);
  if (key === "size_mm") return `${num(Math.round(value * 10) / 10)} mm`;
  if (key === "needs_review") return value ? T.yes : T.no;
  if (key === "source") return T.sources[value] || value;
  if (key === "id") return `#${value}`;
  return String(value);
}

const rows = computed(() => (event.value ? ORDER.map((k) => ({ k, v: show(k, event.value[k]) })).filter((r) => r.v != null) : []));

async function loadEvent() {
  failed.value = false;
  event.value = panel.event;
  try {
    event.value = (await api(`/api/events/${panel.id}`)).event;
  } catch {
    failed.value = true;
  }
}

async function loadDrill() {
  drill.value = null;
  const query = { size: 50, ...panel.drill.query };
  const body = await api("/api/events", { query }).catch(() => ({ events: [], total: 0 }));
  drill.value = body;
  back.value = panel.drill;
}

function drawCrop() {
  const x = fresh.value;
  if (!x || !crop.value) return;
  const img = new Image();
  img.onload = () => {
    const [x0, y0, x1, y1] = x.box;
    let side = Math.max(x1 - x0 + 1, y1 - y0 + 1) * 1.15;
    side = Math.min(side, img.naturalWidth, img.naturalHeight);
    const cx = (x0 + x1 + 1) / 2;
    const cy = (y0 + y1 + 1) / 2;
    const left = Math.min(Math.max(cx - side / 2, 0), img.naturalWidth - side);
    const top = Math.min(Math.max(cy - side / 2, 0), img.naturalHeight - side);
    const g = crop.value.getContext("2d");
    g.drawImage(img, Math.round(left), Math.round(top), Math.round(side), Math.round(side), 0, 0, 224, 224);
  };
  img.src = x.src;
}

function connect() {
  const p = panel.drill?.point;
  const el = line.value;
  const sheet = dialog.value?.querySelector(".sheet");
  if (!p || !el || !sheet) return;
  const r = sheet.getBoundingClientRect();
  const tx = r.left;
  const ty = r.top + 56;
  const dx = tx - p.x;
  const dy = ty - p.y;
  const len = Math.hypot(dx, dy);
  el.style.left = `${p.x}px`;
  el.style.top = `${p.y}px`;
  el.style.width = `${len}px`;
  el.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
  el.hidden = false;
  if (!reducedMotion()) el.firstElementChild.animate([{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }], { duration: 420, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)", fill: "backwards" });
}

async function refresh() {
  if (panel.mode === "event") {
    await loadEvent();
    await nextTick();
    drawCrop();
  } else if (panel.mode === "drill") {
    await loadDrill();
    await nextTick();
    connect();
  }
}

function openInHistory() {
  const query = { ...panel.drill.query };
  closePanel();
  router.push({ path: "/historico", query });
}

function onCancel(e) {
  e.preventDefault();
  closePanel();
}

function onClick(e) {
  if (e.target === dialog.value) closePanel();
}

onMounted(() => {
  dialog.value.showModal();
  refresh();
});
watch(() => [panel.mode, panel.id, panel.drill, panel.replay], refresh);
onBeforeUnmount(() => dialog.value?.open && dialog.value.close());
</script>

<template>
  <dialog ref="dialog" class="side-panel" :aria-label="title" @cancel="onCancel" @click="onClick">
    <span ref="line" class="drill-line" hidden aria-hidden="true"><span></span></span>
    <section class="sheet instrument">
      <header class="sheet-head">
        <h2>{{ title }}</h2>
        <button class="icon-btn" type="button" :aria-label="T.close" @click="closePanel">
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
        </button>
      </header>

      <template v-if="panel.mode === 'event'">
        <p v-if="failed" class="notice error" role="alert">{{ T.loadFail }}</p>
        <div v-else-if="event" class="inspect">
          <div class="inspect-chips">
            <span class="chip" :data-state="fresh ? 'concluido' : 'ativo'">{{ fresh ? T.fresh : T.stored }}</span>
            <span v-if="event.is_demo" class="chip" data-state="demo">{{ t.control.chips.demo }}</span>
            <span v-if="event.decided_by === 'simulacao'" class="chip" data-state="simulacao">{{ t.control.chips.simulacao }}</span>
            <span v-if="event.needs_review" class="chip" data-state="analisando">{{ t.control.chips.revisao }}</span>
          </div>
          <figure v-if="fresh" class="inspect-shot">
            <canvas ref="crop" class="inspector-shot" width="224" height="224" role="img" :aria-label="T.crop"></canvas>
            <figcaption><strong>{{ T.crop }}</strong> {{ T.cropNote }}</figcaption>
          </figure>
          <figure v-else-if="event.image" class="inspect-shot">
            <img class="inspector-shot" :src="`/api/events/${event.id}/image`" :alt="fill(t.control.history.thumb, { id: event.id })" width="224" height="168" />
            <figcaption><strong>{{ T.photo }}</strong> {{ T.photoNote }}</figcaption>
          </figure>
          <div class="inspect-verdict" :class="tone">
            <ConfidenceRing v-if="event.confidence != null" :value="event.confidence" :tone="tone" :label="`${T.fields.confidence} ${confidence(event.confidence)}`" />
            <p class="inspect-class">{{ show("label", event.label) || (event.is_good ? t.classes.boa : deformityName(event.deformity_type)) }}</p>
          </div>
          <dl class="inspect-fields" v-trace="fill(fresh ? T.traceFresh : T.traceStored, { id: event.id })">
            <div v-for="r in rows" :key="r.k" :data-field="r.k">
              <dt>{{ T.fields[r.k] }}</dt>
              <dd class="num">{{ r.v }}</dd>
            </div>
          </dl>
          <div v-if="fresh" class="probs">
            <p class="probs-title">{{ T.probs }}</p>
            <div v-for="(p, c) in fresh.probs" :key="c" class="prob-row" :class="TONE[c]">
              <span class="prob-name">{{ t.classes[c] || c }}</span>
              <span class="prob-bar" aria-hidden="true"><span :style="{ transform: `scaleX(${p})` }"></span></span>
              <span class="prob-value">{{ confidence(p) }}</span>
            </div>
            <p class="hint num">{{ T.box }}: {{ fresh.box.join(", ") }}</p>
          </div>
          <p v-else class="hint">{{ T.onlyStored }}</p>
          <button v-if="back" class="btn btn-secondary btn-sm" type="button" @click="openDrill(back)">{{ T.back }}</button>
        </div>
        <div v-else class="sheet-loading" aria-hidden="true"><span></span><span></span><span></span></div>
      </template>

      <template v-else-if="panel.mode === 'drill'">
        <div v-if="drill" class="drill">
          <p class="hint num" v-trace="fill(t.control.history.trace, { filter: panel.drill.trace || '', n: num(drill.total) })">{{ fill(t.control.drill.total, { n: num(drill.total), k: num(drill.events.length) }) }}</p>
          <p v-if="drill.demo" class="chip" data-state="demo">{{ t.control.chips.demo }}</p>
          <ul v-if="drill.events.length" class="drill-list">
            <li v-for="e in drill.events" :key="e.id">
              <button type="button" class="drill-row" @click="openEventId(e.id, $event.currentTarget)">
                <span class="num">#{{ e.id }}</span>
                <span>{{ show("label", e.label) || (e.is_good ? t.classes.boa : deformityName(e.deformity_type)) }}</span>
                <span class="num">{{ e.confidence == null ? "—" : confidence(e.confidence) }}</span>
                <span class="num muted">{{ show("timestamp", e.timestamp) }}</span>
              </button>
            </li>
          </ul>
          <p v-else class="hint">{{ t.control.drill.empty }}</p>
          <button class="btn btn-secondary btn-sm" type="button" @click="openInHistory">{{ t.control.drill.open }}</button>
        </div>
        <div v-else class="sheet-loading" aria-hidden="true"><span></span><span></span><span></span></div>
      </template>

      <LotReplay v-else-if="panel.mode === 'replay'" :key="panel.replay.lot" :replay="panel.replay" />
    </section>
  </dialog>
</template>
