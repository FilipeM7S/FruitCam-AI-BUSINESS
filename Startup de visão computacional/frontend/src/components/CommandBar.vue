<script setup>
import "../control.css";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api.js";
import { commands, openEventId, openReplay } from "../control.js";
import { motion, setMotion, setTheme, theme } from "../media.js";
import { fill, t } from "../strings.js";

const T = t.control.commands;
const router = useRouter();
const dialog = ref(null);
const input = ref(null);
const q = ref("");
const active = ref(0);
const sectors = ref([]);
const lots = ref([]);
const loading = ref(true);
let back = null;

const PAGES = [
  ["/", t.app.navLine],
  ["/inspecao", t.app.navAnalyze],
  ["/painel", t.app.navDashboard],
  ["/historico", t.app.navHistory],
  ["/como-funciona", t.app.navHow],
  ["/creditos", t.app.navCredits],
];

const fold = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

const all = computed(() => {
  const go = (path, query) => () => router.push({ path, query });
  const items = PAGES.map(([path, label]) => ({ group: T.groups.pages, label, run: go(path) }));
  for (const s of sectors.value) {
    items.push({ group: T.groups.filters, label: fill(T.painelSector, { s }), run: go("/painel", { sector: s, source: "all" }) });
    items.push({ group: T.groups.filters, label: fill(T.historySector, { s }), run: go("/historico", { sector: s, source: "all" }) });
  }
  for (const p of ["week", "month"]) items.push({ group: T.groups.filters, label: fill(T.painelPeriod, { p: t.filters[p].toLowerCase() }), run: go("/painel", { period: p }) });
  for (const s of ["real", "demo", "all"]) items.push({ group: T.groups.filters, label: fill(T.painelSource, { s: t.filters[s] }), run: go("/painel", { source: s }) });
  for (const f of Object.keys(t.fruits)) items.push({ group: T.groups.filters, label: fill(T.historyFruit, { f: t.fruits[f] }), run: go("/historico", { fruit_type: f, source: "all" }) });
  items.push({ group: T.groups.filters, label: T.historyReview, run: go("/historico", { review: "yes", source: "all" }) });
  for (const l of lots.value) items.push({ group: T.groups.lots, label: fill(T.lot, { lot: l.lot, camera: l.camera, n: l.n.toLocaleString("pt-BR") }), run: () => openReplay({ camera: l.camera, lot: l.lot, source: l.demo ? "demo" : "real" }) });
  items.push({ group: T.groups.display, label: T.theme, run: () => setTheme(!theme.dark) });
  items.push({ group: T.groups.display, label: T.motion, run: () => setMotion(!motion.reduced) });
  return items;
});

const results = computed(() => {
  const id = /^#?(\d{1,9})$/.exec(q.value.trim());
  const list = id ? [{ group: T.groups.events, label: fill(T.event, { id: id[1] }), run: () => openEventId(Number(id[1])) }] : [];
  const words = fold(q.value).split(/\s+/).filter(Boolean);
  return [...list, ...all.value.filter((it) => words.every((w) => fold(`${it.group} ${it.label}`).includes(w)))].slice(0, 40);
});

watch(q, () => (active.value = 0));

function close() {
  commands.open = false;
  nextTick(() => back?.focus?.());
}

function pick(item) {
  close();
  item.run();
}

function onKey(e) {
  const n = results.value.length;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    if (!n) return;
    active.value = (active.value + (e.key === "ArrowDown" ? 1 : n - 1)) % n;
    nextTick(() => dialog.value.querySelector(`#cmd-${active.value}`)?.scrollIntoView({ block: "nearest" }));
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (results.value[active.value]) pick(results.value[active.value]);
  }
}

onMounted(async () => {
  back = document.activeElement;
  dialog.value.showModal();
  input.value.focus();
  const [s, l] = await Promise.allSettled([api("/api/sectors", { query: { source: "all" } }), api("/api/events", { query: { source: "all", kind: "camera", shape: "lots" } })]);
  sectors.value = s.status === "fulfilled" ? s.value.sectors : [];
  lots.value = l.status === "fulfilled" ? l.value.lots : [];
  loading.value = false;
});
</script>

<template>
  <dialog ref="dialog" class="command-bar" :aria-label="T.label" @cancel.prevent="close" @click.self="close">
    <div class="cmd-box instrument">
      <input
        ref="input"
        v-model="q"
        class="cmd-input"
        type="text"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded="true"
        aria-controls="cmd-list"
        :aria-activedescendant="results.length ? `cmd-${active}` : undefined"
        :aria-label="T.label"
        :placeholder="T.placeholder"
        autocomplete="off"
        spellcheck="false"
        @keydown="onKey"
      />
      <ul id="cmd-list" class="cmd-list" role="listbox" :aria-label="T.label">
        <li
          v-for="(it, k) in results"
          :id="`cmd-${k}`"
          :key="`${it.group}-${it.label}`"
          role="option"
          class="cmd-item"
          :class="{ active: k === active }"
          :aria-selected="k === active"
          @mousemove="active = k"
          @click="pick(it)"
        >
          <span class="cmd-group">{{ it.group }}</span>
          <span>{{ it.label }}</span>
        </li>
      </ul>
      <p v-if="!results.length" class="hint" role="status">{{ T.empty }}</p>
      <p class="cmd-help"><span v-if="loading">{{ T.loading }} · </span>{{ T.help }}</p>
    </div>
  </dialog>
</template>
