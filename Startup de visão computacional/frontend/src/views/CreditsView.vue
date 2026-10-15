<script setup>
import legal from "../../../legal/site.json";
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

    <section id="proprio" class="section">
      <header class="section-head">
        <h2>{{ t.credits.firstParty }}</h2>
      </header>
      <ul class="credit-list">
        <li v-for="c in legal.own" :id="c.id" :key="c.id" class="credit paper">
          <h3>{{ c.title }}</h3>
          <p class="attribution">{{ c.note }}</p>
          <dl>
            <div><dt>{{ t.credits.license }}</dt><dd>{{ c.license }}</dd></div>
            <div><dt>{{ t.credits.source }}</dt><dd>{{ c.source }}</dd></div>
            <div v-if="c.files"><dt>{{ t.credits.files }}</dt><dd>{{ c.files }}</dd></div>
          </dl>
        </li>
      </ul>
    </section>

    <section id="midia" class="section">
      <header class="section-head">
        <h2>{{ t.credits.thirdParty }}</h2>
      </header>
      <ul class="credit-list">
        <li v-for="c in legal.media" :id="c.id" :key="c.id" class="credit paper">
          <h3>{{ c.title }}</h3>
          <p class="attribution">{{ c.attribution }}</p>
          <dl>
            <div><dt>{{ t.credits.author }}</dt><dd>{{ c.author }}</dd></div>
            <div><dt>{{ t.credits.license }}</dt><dd><a :href="c.license_url" rel="license noopener" target="_blank">{{ c.license }}</a></dd></div>
            <div><dt>{{ t.credits.source }}</dt><dd><a :href="c.source_url" rel="noopener" target="_blank">{{ decodeURI(c.source_url) }}</a></dd></div>
            <div><dt>{{ t.credits.date }}</dt><dd>{{ c.date ? c.date.split(" ")[0] : "—" }}</dd></div>
            <div><dt>{{ t.credits.retrieved }}</dt><dd>{{ c.retrieved }}</dd></div>
            <div><dt>{{ t.credits.modifications }}</dt><dd>{{ c.modifications }}</dd></div>
            <div><dt>{{ t.credits.usedIn }}</dt><dd>{{ c.used_in.join(" · ") }}</dd></div>
            <div><dt>{{ t.credits.files }}</dt><dd>{{ c.files }}</dd></div>
          </dl>
        </li>
      </ul>
    </section>

    <section id="dados" class="section">
      <header class="section-head">
        <h2>{{ t.credits.dataTitle }}</h2>
        <p>{{ t.credits.dataLead }}</p>
      </header>
      <ul class="credit-list">
        <li v-for="d in legal.datasets" :id="`dados-${d.id}`" :key="d.id" class="credit paper">
          <h3>{{ d.title }}</h3>
          <p class="attribution">{{ d.attribution }}</p>
          <dl>
            <div><dt>{{ t.credits.authors }}</dt><dd>{{ d.authors }}</dd></div>
            <div><dt>{{ t.credits.license }}</dt><dd><a :href="d.license_url" rel="license noopener" target="_blank">{{ d.license }}</a></dd></div>
            <div><dt>{{ t.credits.source }}</dt><dd><a :href="d.page" rel="noopener" target="_blank">{{ d.page }}</a></dd></div>
            <div><dt>{{ t.credits.use }}</dt><dd>{{ d.use }}</dd></div>
            <div><dt>{{ t.credits.modifications }}</dt><dd>{{ d.modifications }}</dd></div>
            <div v-for="x in d.derived" :key="x.title"><dt>{{ t.credits.derived }}</dt><dd>{{ x.title }} ({{ x.used_in }}). {{ x.modifications }} {{ x.note }}</dd></div>
          </dl>
        </li>
      </ul>
    </section>

    <section id="tipografia" class="section">
      <header class="section-head">
        <h2>{{ t.credits.typeTitle }}</h2>
        <p>{{ t.credits.typeLead }}</p>
      </header>
      <ul class="credit-list">
        <li v-for="f in legal.fonts" :id="f.id" :key="f.id" class="credit paper">
          <h3>{{ f.title }}</h3>
          <dl>
            <div><dt>{{ t.credits.author }}</dt><dd>{{ f.author }}</dd></div>
            <div><dt>{{ t.credits.license }}</dt><dd><a :href="f.license_url" rel="license noopener" target="_blank">{{ f.license }}</a></dd></div>
            <div><dt>{{ t.credits.source }}</dt><dd><a :href="f.source_url" rel="noopener" target="_blank">{{ f.source_url }}</a></dd></div>
            <div><dt>{{ t.credits.modifications }}</dt><dd>{{ f.modifications }}</dd></div>
            <div><dt>{{ t.credits.usedIn }}</dt><dd>{{ f.used_in }}</dd></div>
          </dl>
        </li>
      </ul>
    </section>

    <section id="software" class="section">
      <header class="section-head">
        <h2>{{ t.credits.software }}</h2>
        <p>{{ t.credits.softwareLead }}</p>
      </header>
      <ul class="credit-list software-list">
        <li v-for="s in legal.software" :key="s.name" class="credit paper">
          <h3><a :href="s.url" rel="noopener" target="_blank">{{ s.name }}</a></h3>
          <dl>
            <div><dt>{{ t.credits.license }}</dt><dd>{{ s.license }}</dd></div>
            <div><dt>{{ t.credits.role }}</dt><dd>{{ s.role }}</dd></div>
            <div v-if="s.note"><dt>{{ t.credits.note }}</dt><dd>{{ s.note }}</dd></div>
          </dl>
        </li>
      </ul>
    </section>

    <section id="regras" class="section">
      <header class="section-head">
        <h2>{{ t.credits.rules }}</h2>
      </header>
      <ul class="credit-rules paper">
        <li v-for="rule in legal.rules" :key="rule">{{ rule }}</li>
      </ul>
    </section>
  </section>
</template>
