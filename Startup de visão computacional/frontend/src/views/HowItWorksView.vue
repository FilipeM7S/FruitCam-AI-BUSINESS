<script setup>
import LoopVideo from "../components/LoopVideo.vue";
import PipelineAnimation from "../components/PipelineAnimation.vue";
import PipelineFlow from "../components/PipelineFlow.vue";
import ResponsiveImage from "../components/ResponsiveImage.vue";
import figures from "../figures.json";
import media from "../media.json";
import { url, vReveal } from "../media.js";
import { num, pct } from "../format.js";
import { fill, t } from "../strings.js";

const list = figures.order.map((id) => ({ id, ...figures.items[id] }));
const ev = figures.modelEval;
const tt = ev.test;
const measured = fill(t.how.measured, { n: num(tt.n), photos: num(tt.photos), acc: pct(tt.accuracy), lo: pct(tt.accuracy_ci95[0]), hi: pct(tt.accuracy_ci95[1]), base: pct(tt.majority_baseline_accuracy), bal: pct(tt.balanced_accuracy) });
const perClass = fill(t.how.perClass, { boa: pct(tt.recall.boa), poor: pct(tt.recall.baixa_qualidade), rotten: pct(tt.recall.podre), rg: pct(tt.rotten_as_good.k / tt.rotten_as_good.n), rglo: pct(tt.rotten_as_good.rate_ci95[0]), rghi: pct(tt.rotten_as_good.rate_ci95[1]) });
const cut = tt.field_photo_threshold;
const review = tt.with_reject.threshold != null
  ? fill(t.how.review, { thr: pct(tt.with_reject.threshold, 0), cov: pct(tt.with_reject.coverage, 0), accd: pct(tt.with_reject.accuracy_on_accepted) })
  : cut
    ? fill(t.how.reviewMeasured, { thr: pct(cut.threshold, 0), cov: pct(cut.coverage, 0), accd: pct(cut.accuracy_on_accepted) })
    : t.how.reviewNone;
const rot = ev.rotten;
const rotten = rot && rot.tried
  ? fill(rot.holds ? t.how.rottenHolds : t.how.rottenFails, { cut: pct(rot.cut, 0), p0: pct(rot.now.rotten_precision), p1: pct(rot.tried.rotten_precision), r0: pct(rot.now.rotten_recall), r1: pct(rot.tried.rotten_recall), g0: pct(rot.now.rotten_called_good), g1: pct(rot.tried.rotten_called_good), limit: pct(rot.limit, 0), n: num(rot.n_rotten) })
  : "";
const beltAfter = ev.belt.with_review.n_decided ? fill(t.how.beltReview, { cov: pct(ev.belt.with_review.coverage, 0), accd: pct(ev.belt.with_review.accuracy_on_decided) }) : t.how.beltReviewNone;
const beltText = fill(t.how.beltText, { crossed: num(ev.belt.counting.fruits_that_crossed_the_line), counted: num(ev.belt.counting.counted), double: num(ev.belt.counting.double_counts), acc: pct(ev.belt.multi_view.accuracy), direct: pct(tt.accuracy), after: beltAfter });
const hasDemo = Boolean(media.items.demo);
</script>

<template>
  <section class="page how">
    <header class="page-head page-banner how-head">
      <ResponsiveImage id="banner-pacajus" eager cover :caption="false" sizes="(min-width: 1160px) 1096px, 100vw" />
      <div class="banner-text page-head-text">
        <h1>{{ t.how.title }}</h1>
        <p class="lead">{{ t.how.lead }}</p>
        <p class="bg-credit">
          <RouterLink class="illustrative" :to="{ path: '/creditos', hash: '#caju-pacajus' }">{{ t.media.illustrative }}<span class="visually-hidden">{{ t.media.seeCredits }}</span></RouterLink>
        </p>
      </div>
    </header>

    <section class="section how-section">
      <header class="section-head">
        <h2>{{ t.how.pipelineTitle }}</h2>
      </header>
      <PipelineFlow />
      <PipelineAnimation />
    </section>

    <section class="section how-section">
      <header class="section-head">
        <h2>{{ t.how.figuresTitle }}</h2>
        <p>{{ t.how.figuresLead }}</p>
      </header>
      <div class="figure-list">
        <figure v-for="f in list" :id="f.id" :key="f.id" v-reveal class="sci-figure paper" :data-label="f.label">
          <div class="figure-scroll" role="region" tabindex="0" :aria-label="`${t.how.figure} ${f.number}: ${f.title}`">
            <img :src="url(f.web)" :width="f.width" :height="f.height" :alt="f.alt" loading="lazy" decoding="async" />
          </div>
          <p class="scroll-hint" aria-hidden="true">{{ t.how.scrollHint }}</p>
          <figcaption>
            <span class="badge" :class="`label-${f.label}`">{{ t.how.labels[f.label] }}</span>
            <p><strong>{{ t.how.figure }} {{ f.number }}.</strong> {{ f.caption }}</p>
            <p class="downloads">
              {{ t.how.download }}:
              <a :href="url(f.svg)" download>{{ t.how.downloadSvg }}</a>
              ·
              <a :href="url(f.png)" download>{{ t.how.downloadPng }}</a>
            </p>
          </figcaption>
        </figure>
      </div>
    </section>

    <section id="qualidade" class="section how-section">
      <header class="section-head">
        <h2>{{ t.how.qualityTitle }}</h2>
      </header>
      <div v-reveal class="quality paper">
        <p class="warn-text">{{ t.how.dataIssue }}</p>
        <p>{{ measured }}</p>
        <p>{{ perClass }}</p>
        <p>{{ review }}</p>
        <p v-if="rotten">{{ rotten }}</p>
        <p>{{ beltText }}</p>
        <p class="warn-text">{{ t.how.limits }}</p>
      </div>
      <h3>{{ t.how.pendingTitle }}</h3>
      <ul class="pending">
        <li v-for="p in t.how.pending" :key="p.title" v-reveal class="pending-item paper">
          <span class="badge warn">{{ t.how.notEvaluated }}</span>
          <strong>{{ p.title }}</strong>
          <span>{{ p.text }}</span>
        </li>
      </ul>
    </section>

    <section v-if="hasDemo" class="section how-section">
      <header class="section-head">
        <h2>{{ t.how.videoTitle }}</h2>
      </header>
      <LoopVideo id="demo" />
    </section>

    <section class="section how-section split">
      <div v-reveal class="paper split-card">
        <h2>{{ t.how.verifiedTitle }}</h2>
        <ul>
          <li v-for="item in t.how.verified" :key="item">{{ item }}</li>
        </ul>
      </div>
      <div v-reveal class="paper split-card">
        <h2>{{ t.how.notVerifiedTitle }}</h2>
        <ul>
          <li v-for="item in t.how.notVerified" :key="item">{{ item }}</li>
        </ul>
      </div>
    </section>
  </section>
</template>
