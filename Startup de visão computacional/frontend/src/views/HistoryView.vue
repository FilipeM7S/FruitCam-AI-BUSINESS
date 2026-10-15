<script setup>
import "../control.css";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../api.js";
import LoopVideo from "../components/LoopVideo.vue";
import { openEventId, vTrace } from "../control.js";
import { confidence, deformityName, fruitName, num } from "../format.js";
import { mediaItem } from "../media.js";
import { fill, t } from "../strings.js";

const T = t.control.history;
const KEYS = ["source", "kind", "sector", "fruit_type", "label", "review", "lot", "start", "end"];
const SIZE = 50;
const route = useRoute();
const router = useRouter();
const f = reactive({ source: "real", kind: "", sector: "", fruit_type: "", label: "", review: "", lot: "", start: "", end: "", ...pickQuery(route.query) });
const page = ref(1);
const body = ref(null);
const loading = ref(false);
const failed = ref(false);
const sectors = ref([]);
const picked = reactive(new Map());
const hasVideo = Boolean(mediaItem("primeira-analise"));
let request = 0;

function pickQuery(q) {
  return Object.fromEntries(KEYS.filter((k) => typeof q[k] === "string").map((k) => [k, q[k]]));
}

const query = computed(() => Object.fromEntries(Object.entries(f).filter(([, v]) => v)));
const filterText = computed(() => Object.entries(query.value).map(([k, v]) => `${k}=${v}`).join(" · ") || "source=real");
const pages = computed(() => Math.max(1, Math.ceil((body.value?.total || 0) / SIZE)));
const rows = computed(() => body.value?.events || []);
const pageAll = computed(() => rows.value.length > 0 && rows.value.every((e) => picked.has(e.id)));
const selection = computed(() => {
  const list = [...picked.values()];
  const by = {};
  for (const e of list) by[cls(e)] = (by[cls(e)] || 0) + 1;
  const conf = list.filter((e) => e.confidence != null);
  return { n: list.length, by, mean: conf.length ? conf.reduce((s, e) => s + e.confidence, 0) / conf.length : null };
});

function cls(e) {
  if (e.needs_review) return "revisar";
  if (e.label) return e.label;
  return e.is_good ? "boa" : e.deformity_type || "revisar";
}

function classText(e) {
  return t.classes[cls(e)] || deformityName(cls(e));
}

async function load() {
  const id = ++request;
  loading.value = true;
  failed.value = false;
  try {
    const r = await api("/api/events", { query: { ...query.value, page: page.value, size: SIZE } });
    if (id === request) body.value = r;
  } catch {
    if (id === request) failed.value = true;
  } finally {
    if (id === request) loading.value = false;
  }
}

async function loadSectors() {
  sectors.value = (await api("/api/sectors", { query: { source: f.source } }).catch(() => ({ sectors: [] }))).sectors;
}

watch(
  () => JSON.stringify(query.value),
  () => {
    page.value = 1;
    router.replace({ query: query.value });
    load();
  },
);
watch(page, load);
watch(() => f.source, loadSectors);
watch(
  () => route.query,
  (q) => {
    const next = { source: "real", kind: "", sector: "", fruit_type: "", label: "", review: "", lot: "", start: "", end: "", ...pickQuery(q) };
    if (JSON.stringify(next) !== JSON.stringify({ ...f })) Object.assign(f, next);
  },
);
load();
loadSectors();

function toggle(e) {
  if (picked.has(e.id)) picked.delete(e.id);
  else picked.set(e.id, e);
}

function togglePage() {
  const all = pageAll.value;
  for (const e of rows.value) {
    if (all) picked.delete(e.id);
    else picked.set(e.id, e);
  }
}

function csvCell(v) {
  const s = v == null ? "" : String(v);
  return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function exportCsv() {
  const cols = ["id", "timestamp", "sector", "fruit_type", "label", "is_good", "deformity_type", "confidence", "needs_review", "source", "camera", "lot", "track_id", "size_mm", "decided_by", "model_version", "is_demo"];
  const lines = [cols.join(";"), ...[...picked.values()].map((e) => cols.map((c) => csvCell(e[c])).join(";"))];
  const href = URL.createObjectURL(new Blob([`﻿${lines.join("\n")}`], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href, download: `fruitcam-selecao-${picked.size}.csv` });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 10000);
}

function when(iso) {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}
</script>

<template>
  <section class="page history">
    <header class="page-head">
      <div class="page-head-text">
        <h1>{{ T.title }}</h1>
        <p class="lead">{{ T.lead }}</p>
      </div>
      <div class="page-head-actions">
        <span v-if="body?.demo" class="chip" data-state="demo">{{ t.control.chips.demo }}</span>
        <span class="chip" :data-state="loading ? 'analisando' : body?.total ? 'ativo' : 'sem-dados'">{{ loading ? t.control.chips.analisando : body?.total ? t.control.chips.ativo : t.control.chips.semDados }}</span>
      </div>
    </header>

    <form class="filters history-filters" :aria-label="T.filters" @submit.prevent>
      <label class="field">
        <span>{{ t.filters.source }}</span>
        <select v-model="f.source">
          <option value="real">{{ t.filters.real }}</option>
          <option value="demo">{{ t.filters.demo }}</option>
          <option value="all">{{ t.filters.all }}</option>
        </select>
      </label>
      <label class="field">
        <span>{{ T.kind }}</span>
        <select v-model="f.kind">
          <option value="">{{ T.any }}</option>
          <option v-for="(label, k) in T.kinds" :key="k" :value="k">{{ label }}</option>
        </select>
      </label>
      <label class="field">
        <span>{{ t.filters.sector }}</span>
        <select v-model="f.sector">
          <option value="">{{ t.filters.allSectors }}</option>
          <option v-for="s in sectors" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label class="field">
        <span>{{ t.upload.fruit }}</span>
        <select v-model="f.fruit_type">
          <option value="">{{ T.any }}</option>
          <option v-for="(label, k) in t.fruits" :key="k" :value="k">{{ label }}</option>
        </select>
      </label>
      <label class="field">
        <span>{{ T.label }}</span>
        <select v-model="f.label">
          <option value="">{{ T.any }}</option>
          <option v-for="k in ['boa', 'baixa_qualidade', 'podre']" :key="k" :value="k">{{ t.classes[k] }}</option>
        </select>
      </label>
      <label class="field">
        <span>{{ T.review }}</span>
        <select v-model="f.review">
          <option value="">{{ T.any }}</option>
          <option value="yes">{{ T.reviewYes }}</option>
          <option value="no">{{ T.reviewNo }}</option>
        </select>
      </label>
      <label class="field">
        <span>{{ T.lot }}</span>
        <input v-model.lazy.trim="f.lot" maxlength="40" autocomplete="off" />
      </label>
      <label class="field">
        <span>{{ t.filters.start }}</span>
        <input v-model="f.start" type="date" :max="f.end || undefined" />
      </label>
      <label class="field">
        <span>{{ t.filters.end }}</span>
        <input v-model="f.end" type="date" :min="f.start || undefined" />
      </label>
    </form>

    <div class="history-bar" role="region" :aria-label="T.summary">
      <p class="num history-total" v-trace="fill(T.trace, { filter: filterText, n: num(body?.total ?? 0) })">{{ fill(T.total, { n: num(body?.total ?? 0) }) }}</p>
      <template v-if="selection.n">
        <p class="num history-selected" role="status">
          {{ fill(T.selected, { n: num(selection.n) }) }} ·
          <span v-for="(n, c) in selection.by" :key="c">{{ t.classes[c] || c }} {{ num(n) }} · </span>
          <span v-if="selection.mean != null">{{ fill(T.meanConfidence, { c: confidence(selection.mean) }) }}</span>
        </p>
        <button class="btn btn-secondary btn-sm" type="button" @click="exportCsv">{{ T.export }}</button>
        <button class="btn btn-ghost btn-sm" type="button" @click="picked.clear()">{{ T.clear }}</button>
      </template>
    </div>

    <p v-if="failed" class="notice error" role="alert">{{ t.control.inspector.loadFail }}</p>
    <div v-else-if="body && !rows.length" class="empty-state history-empty">
      <p class="notice info">{{ f.source === "real" && Object.keys(query).length === 1 ? T.emptyReal : T.empty }}</p>
      <LoopVideo v-if="hasVideo" id="primeira-analise" :badge="t.media.appRecording" />
    </div>
    <div v-else-if="body" class="history-scroll" role="region" tabindex="0" :aria-label="T.title" :aria-busy="loading">
      <table class="history-table">
        <thead>
          <tr>
            <th scope="col"><input type="checkbox" :checked="pageAll" :aria-label="T.selectPage" @change="togglePage" /></th>
            <th scope="col">{{ T.cols.id }}</th>
            <th scope="col">{{ T.cols.when }}</th>
            <th scope="col">{{ T.cols.sector }}</th>
            <th scope="col">{{ T.cols.fruit }}</th>
            <th scope="col">{{ T.cols.label }}</th>
            <th scope="col">{{ T.cols.confidence }}</th>
            <th scope="col">{{ T.cols.source }}</th>
            <th scope="col">{{ T.cols.lot }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in rows" :key="e.id" :class="{ picked: picked.has(e.id) }">
            <td><input type="checkbox" :checked="picked.has(e.id)" :aria-label="fill(T.select, { id: e.id })" @change="toggle(e)" /></td>
            <td>
              <button type="button" class="row-open num" :aria-label="fill(T.open, { id: e.id })" @click="openEventId(e.id, $event.currentTarget)">
                <img v-if="e.image" class="row-thumb" :src="`/api/events/${e.id}/image`" :alt="fill(T.thumb, { id: e.id })" width="32" height="24" loading="lazy" decoding="async" />#{{ e.id }}
              </button>
            </td>
            <td class="num">{{ when(e.timestamp) }}</td>
            <td>{{ e.sector }}</td>
            <td>{{ fruitName(e.fruit_type) }}</td>
            <td><span class="class-tag" :class="cls(e)">{{ classText(e) }}</span></td>
            <td class="num">{{ e.confidence == null ? "—" : confidence(e.confidence) }}</td>
            <td>{{ T.kinds[e.source] || e.source }}<span v-if="e.is_demo" class="chip mini" data-state="demo">{{ t.control.chips.demo }}</span></td>
            <td class="num">{{ e.lot || "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="sheet-loading" aria-hidden="true"><span></span><span></span><span></span></div>

    <nav v-if="pages > 1" class="pager" :aria-label="fill(T.page, { p: page, n: pages })">
      <button class="btn btn-secondary btn-sm" type="button" :disabled="page <= 1" @click="page--">{{ T.prev }}</button>
      <span class="num">{{ fill(T.page, { p: num(page), n: num(pages) }) }}</span>
      <button class="btn btn-secondary btn-sm" type="button" :disabled="page >= pages" @click="page++">{{ T.next }}</button>
    </nav>
  </section>
</template>
