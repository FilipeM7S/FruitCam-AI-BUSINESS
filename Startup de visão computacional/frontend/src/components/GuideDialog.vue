<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { t } from "../strings.js";

const dialog = ref(null);
const opener = ref(null);
const body = ref(null);

function typing(el) {
  return el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);
}

async function open() {
  if (dialog.value.open) return;
  dialog.value.showModal();
  await nextTick();
  body.value.scrollTop = 0;
}

function close() {
  dialog.value.close();
}

function onKey(e) {
  if (e.key === "?" && !e.ctrlKey && !e.metaKey && !e.altKey && !typing(document.activeElement)) {
    e.preventDefault();
    open();
  }
}

function onBackdrop(e) {
  if (e.target === dialog.value) close();
}

function jump(id) {
  body.value.querySelector(`#help-${id}`)?.scrollIntoView({ block: "start" });
  body.value.querySelector(`#help-${id} h3`)?.focus();
}

onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>

<template>
  <button ref="opener" class="help-fab" type="button" :aria-label="t.help.open" :title="t.help.open" aria-haspopup="dialog" @click="open">
    <span aria-hidden="true">?</span>
  </button>
  <dialog ref="dialog" class="help" aria-labelledby="help-title" @click="onBackdrop" @close="opener?.focus()">
    <div ref="body" class="help-body">
      <header class="help-head">
        <span class="help-mark" aria-hidden="true">?</span>
        <div>
          <h2 id="help-title">{{ t.help.title }}</h2>
          <p class="muted">{{ t.help.lead }}</p>
        </div>
        <button class="help-close" type="button" :aria-label="t.help.close" @click="close">
          <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
        </button>
      </header>
      <nav class="help-toc" :aria-label="t.help.contents">
        <a v-for="(s, i) in t.help.sections" :key="s.id" :href="`#help-${s.id}`" @click.prevent="jump(s.id)"><span>{{ i + 1 }}</span>{{ s.title }}</a>
      </nav>
      <section v-for="(s, i) in t.help.sections" :id="`help-${s.id}`" :key="s.id" class="help-section">
        <h3 tabindex="-1"><span class="help-num" aria-hidden="true">{{ i + 1 }}</span>{{ s.title }}</h3>
        <p v-for="b in s.body" :key="b">{{ b }}</p>
      </section>
    </div>
  </dialog>
</template>
