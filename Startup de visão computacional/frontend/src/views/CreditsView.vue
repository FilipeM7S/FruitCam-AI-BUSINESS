<script setup>
import licenses from "../licenses.json";
import { t } from "../strings.js";
</script>

<template>
  <section class="page credits">
    <header class="page-head">
      <div class="page-head-text">
        <h1>{{ t.credits.title }}</h1>
        <p class="lead">{{ t.credits.lead }}</p>
      </div>
    </header>

    <section class="section">
    <header class="section-head">
      <h2>{{ t.credits.thirdParty }}</h2>
    </header>
    <ul class="credit-list">
      <li v-for="c in licenses.third_party" :id="c.id" :key="c.id" class="credit paper">
        <h3>{{ c.title }}</h3>
        <p class="attribution">{{ c.attribution_text }}</p>
        <dl>
          <div><dt>{{ t.credits.author }}</dt><dd>{{ c.author }}</dd></div>
          <div><dt>{{ t.credits.license }}</dt><dd><a :href="c.license_url" rel="license noopener" target="_blank">{{ c.license }}</a></dd></div>
          <div><dt>{{ t.credits.source }}</dt><dd><a :href="c.source_url" rel="noopener" target="_blank">{{ decodeURI(c.source_url) }}</a></dd></div>
          <div><dt>{{ t.credits.date }}</dt><dd>{{ c.date ? c.date.split(" ")[0] : "—" }}</dd></div>
          <div><dt>{{ t.credits.retrieved }}</dt><dd>{{ c.retrieved }}</dd></div>
          <div><dt>{{ t.credits.modifications }}</dt><dd>{{ c.modifications }}</dd></div>
          <div><dt>{{ t.credits.usedIn }}</dt><dd>{{ c.used_in.join(" · ") }}</dd></div>
          <div><dt>{{ t.credits.files }}</dt><dd>{{ c.files.length }}</dd></div>
        </dl>
      </li>
    </ul>
    </section>

    <section class="section">
    <header class="section-head">
      <h2>{{ t.credits.dataTitle }}</h2>
      <p>{{ t.credits.dataLead }}</p>
    </header>
    <ul class="credit-list">
      <li v-for="d in licenses.datasets" :id="`dados-${d.id}`" :key="d.id" class="credit paper">
        <h3>{{ d.title }}</h3>
        <p class="attribution">{{ d.attribution }}</p>
        <dl>
          <div><dt>{{ t.credits.authors }}</dt><dd>{{ d.authors }}</dd></div>
          <div><dt>{{ t.credits.license }}</dt><dd><a :href="d.licence_url" rel="license noopener" target="_blank">{{ d.licence }}</a></dd></div>
          <div><dt>{{ t.credits.source }}</dt><dd><a :href="d.page" rel="noopener" target="_blank">{{ d.page }}</a></dd></div>
          <div><dt>{{ t.credits.use }}</dt><dd>{{ t.credits.datasetUse[d.id].use }}</dd></div>
          <div><dt>{{ t.credits.modifications }}</dt><dd>{{ t.credits.datasetUse[d.id].modifications }}</dd></div>
        </dl>
      </li>
    </ul>
    </section>

    <section class="section">
    <header class="section-head">
      <h2>{{ t.credits.firstParty }}</h2>
    </header>
    <ul class="credit-list">
      <li v-for="c in licenses.first_party" :id="c.id" :key="c.id" class="credit paper">
        <h3>{{ c.title }}</h3>
        <p class="attribution">{{ c.note }}</p>
        <dl>
          <div><dt>{{ t.credits.license }}</dt><dd>{{ c.license }}</dd></div>
          <div><dt>{{ t.credits.source }}</dt><dd>{{ c.source }}</dd></div>
          <div><dt>{{ t.credits.files }}</dt><dd>{{ c.files.length }}</dd></div>
        </dl>
      </li>
    </ul>
    </section>
  </section>
</template>
