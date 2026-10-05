<script setup>
import { computed, onMounted, reactive, ref, shallowRef, watch } from "vue";
import { api } from "../api.js";
import BrandLogo from "../components/BrandLogo.vue";
import ChartBox from "../components/ChartBox.vue";
import StatCard from "../components/StatCard.vue";
import { deformitySpec, forecastSpec, fruitsSpec, gaussianSpecs, growthSpec, overviewSpecs, recurringSpec } from "../charts.js";
import { num } from "../format.js";
import { deformitySeries, forecastSeries, fruitSeries, gaussianSeries, growthRange, growthSeries, overviewSeries, recurringSeries, SMALL_N } from "../series.js";
import { fill, t } from "../strings.js";

const NAMES = ["deformity", "forecast", "fruits", "growth", "recurring", "gaussian", "overview"];
const filters = reactive({ period: "week", sector: "", start: "", end: "", source: "real" });
const results = shallowRef({});
const refreshing = ref(false);
const sectors = ref([]);
const recurringTab = ref("month");
let request = 0;

const data = (n) => results.value[n]?.data;
const ok = (n) => data(n)?.status === "ok";
const demo = computed(() => Object.values(results.value).some((r) => r.data?.demo));
const allEmpty = computed(() => NAMES.every((n) => data(n)?.status === "no_data"));
const small = (title) => ({ text: t.badges.small, tone: "warn", cls: "small-tag", title });
const partial = (n) => ({ text: t.badges.partial, tone: "info", cls: "partial-tag", title: fill(t.cards.growth.excludedTitle, { n: num(n) }) });

async function loadSectors() {
  try {
    sectors.value = (await api("/api/sectors", { query: { source: filters.source } })).sectors;
  } catch {
    sectors.value = [];
  }
  if (filters.sector && !sectors.value.includes(filters.sector)) filters.sector = "";
}

async function load() {
  const id = ++request;
  refreshing.value = Object.keys(results.value).length > 0;
  const query = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
  const settled = await Promise.allSettled(NAMES.map((n) => api(`/api/stats/${n}`, { query })));
  if (id !== request) return;
  results.value = Object.fromEntries(NAMES.map((n, i) => [n, settled[i].status === "fulfilled" ? { data: settled[i].value } : { error: settled[i].reason }]));
  refreshing.value = false;
}

onMounted(async () => {
  await loadSectors();
  load();
});
watch(() => filters.source, loadSectors);
watch(filters, load);

const deformity = computed(() => {
  if (!ok("deformity")) return null;
  const s = deformitySeries(data("deformity"));
  const badges = [];
  if (s.latest && s.latest.n < SMALL_N) badges.push(small(fill(t.badges.smallLatest, { n: s.latest.n })));
  if (s.types.length === 1) badges.push({ text: t.badges.oneType, tone: "info", title: t.cards.deformity.oneTypeHint });
  return { spec: deformitySpec(s), badges };
});

const forecast = computed(() => {
  if (!ok("forecast")) return null;
  const d = data("forecast");
  const items = d.sectors.map((x) => {
    const s = forecastSeries(x, d.labels, d.target_period);
    const reasons = s.reasons.map((c) => fill(t.cards.forecast.reasons[c], { min: d.reliable_min_periods })).join(" · ");
    return {
      key: s.sector,
      s,
      spec: forecastSpec(s, d.period),
      empty: s.ok ? null : { title: t.cards.forecast.emptyTitle, detail: fill(t.cards.forecast.emptyDetail, { n: s.observed, min: d.min_periods, fruits: d.min_fruits }) },
      badges: [{ text: fill(t.badges.n, { n: num(s.fruits) }), cls: "n-badge", title: t.dashboard.fruitsUnit }, ...(s.reliable ? [] : [{ text: t.badges.unreliable, tone: "warn", cls: "unreliable-tag", title: reasons }])],
    };
  });
  const first = Math.max(0, items.findIndex((i) => i.s.ok));
  return { items, steps: items.length ? items[first].spec.steps.map((st) => ({ ...st, target: st.target.selector ? st.target : { ...st.target, chart: first } })) : [] };
});

const fruits = computed(() => {
  if (!ok("fruits")) return null;
  const s = fruitSeries(data("fruits"));
  return { spec: fruitsSpec(s), badges: s.total < SMALL_N ? [small(fill(t.badges.smallTotal, { n: s.total }))] : [] };
});

const growth = computed(() => {
  const g = data("growth");
  if (g?.status !== "ok") return null;
  const range = growthRange(g);
  const badges = [];
  if (g.excluded) badges.push(partial(g.excluded));
  if (g.n_periods < 8) badges.push(small(fill(t.badges.fewPeriods, { n: g.n_periods })));
  return { good: growthSpec(growthSeries(g, "good"), "good", range, g.period), rotten: growthSpec(growthSeries(g, "rotten"), "rotten", range, g.period), badges };
});

const recurring = computed(() => {
  if (!ok("recurring")) return null;
  const s = recurringSeries(data("recurring"), recurringTab.value);
  const badges = [];
  if (s.buckets.length && s.maxN < 2) badges.push(small(fill(t.cards.recurring.smallTitle, { n: s.maxN })));
  if (s.excluded) badges.push(partial(s.excluded));
  return { spec: recurringSpec(s, recurringTab.value), badges, n: s.n, empty: s.buckets.length ? null : { title: t.empty.insufficientTitle, detail: t.cards.recurring.emptyDetail } };
});

const gaussian = computed(() => {
  if (!ok("gaussian")) return null;
  const d = data("gaussian");
  let box = 0;
  let first = -1;
  const items = d.sectors.map((x) => {
    const s = gaussianSeries(x);
    const specs = s.ok ? gaussianSpecs(s) : null;
    if (specs && first < 0) first = box;
    box += specs ? 2 : 1;
    const reasons = s.reasons.map((c) => fill(t.cards.gaussian.reasons[c], { min: d.min_n, alpha: d.alpha })).join(" · ");
    const onlySmall = s.reasons.length === 1 && s.reasons[0] === "small_n";
    return {
      key: s.sector,
      s,
      specs,
      empty: specs ? null : { title: t.cards.gaussian.emptyTitle, detail: fill(t.cards.gaussian.emptyDetail, { n: s.n }) },
      badges: [{ text: fill(t.badges.nPeriods, { n: s.n }), cls: "n-badge", title: t.dashboard.periodsUnit }, ...(s.flagged ? [{ text: onlySmall ? t.badges.small : t.badges.poorFit, tone: "warn", cls: onlySmall ? "small-tag" : "poor-tag", title: reasons }] : [])],
    };
  });
  const steps = first < 0 ? [] : items.find((i) => i.specs).specs.hist.steps.map((st) => ({ ...st, target: st.target.selector ? st.target : { ...st.target, chart: first + (st.target.chart || 0) } }));
  return { items, steps };
});

const overview = computed(() => {
  if (!ok("overview")) return null;
  const d = data("overview");
  const s = overviewSeries(d);
  return { specs: overviewSpecs(s, d.period), badges: s.total < SMALL_N ? [small(fill(t.badges.smallTotal, { n: s.total }))] : [] };
});
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div class="page-head-text">
        <h1>{{ t.dashboard.title }}</h1>
        <p class="lead">{{ t.dashboard.subtitle }}</p>
      </div>
      <div v-if="demo" class="page-head-actions">
        <p class="demo-badge" role="status" :title="t.app.demoBadgeHint">
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 3h6M10 3v6L4 19a1 1 0 0 0 .9 1.5h14.2A1 1 0 0 0 20 19l-6-10V3" /></svg>
          <span>{{ t.app.demoBadge }}</span>
        </p>
      </div>
    </header>

    <form class="filters filter-bar" :aria-label="t.dashboard.filterBar" @submit.prevent>
      <fieldset class="field">
        <legend>{{ t.filters.period }}</legend>
        <div class="segmented small">
          <label v-for="p in ['week', 'month']" :key="p" :class="{ active: filters.period === p }">
            <input v-model="filters.period" type="radio" name="period" :value="p" />
            <span>{{ t.filters[p] }}</span>
          </label>
        </div>
      </fieldset>
      <label class="field">
        <span>{{ t.filters.sector }}</span>
        <select v-model="filters.sector">
          <option value="">{{ t.filters.allSectors }}</option>
          <option v-for="s in sectors" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
    </form>
    <form class="filters filter-more" :aria-label="t.dashboard.filterMore" @submit.prevent>
      <label class="field">
        <span>{{ t.filters.start }}</span>
        <input v-model="filters.start" type="date" :max="filters.end || undefined" />
      </label>
      <label class="field">
        <span>{{ t.filters.end }}</span>
        <input v-model="filters.end" type="date" :min="filters.start || undefined" />
      </label>
      <label class="field">
        <span>{{ t.filters.source }}</span>
        <select v-model="filters.source">
          <option value="real">{{ t.filters.real }}</option>
          <option value="demo">{{ t.filters.demo }}</option>
          <option value="all">{{ t.filters.all }}</option>
        </select>
      </label>
    </form>

    <div v-if="allEmpty && filters.source === 'real' && !filters.sector && !filters.start && !filters.end" class="empty-state">
      <BrandLogo kind="icon" :height="48" />
      <p class="notice info">{{ t.dashboard.noRealData }}</p>
    </div>

    <section class="section" aria-labelledby="sec-overview">
      <header class="section-head">
        <h2 id="sec-overview">{{ t.dashboard.sections.overview.title }}</h2>
        <p>{{ t.dashboard.sections.overview.lead }}</p>
      </header>
      <div class="cards">
        <StatCard stat="overview" :title="t.cards.overview.title" :subtitle="t.cards.overview.subtitle" :result="results.overview" :unit="t.dashboard.fruitsUnit" :badges="overview?.badges" :steps="overview?.specs.steps" :refreshing="refreshing" shape="multiples">
          <div v-if="overview" class="overview-grid">
            <ChartBox :spec="overview.specs.volume" :caption="t.cards.overview.volume" :height="170" />
            <ChartBox :spec="overview.specs.rate" :caption="t.cards.overview.rate" :height="150" />
            <ChartBox :spec="overview.specs.sectors" :caption="t.cards.overview.sectors" :height="150" />
          </div>
        </StatCard>
      </div>
    </section>

    <section class="section" aria-labelledby="sec-now">
      <header class="section-head">
        <h2 id="sec-now">{{ t.dashboard.sections.now.title }}</h2>
        <p>{{ t.dashboard.sections.now.lead }}</p>
      </header>
      <div class="cards">
        <StatCard stat="deformity" :title="t.cards.deformity.title" :subtitle="t.cards.deformity.subtitle" :result="results.deformity" :unit="t.dashboard.rottenUnit" :badges="deformity?.badges" :steps="deformity?.spec.steps" :refreshing="refreshing" shape="bars" span="main">
          <ChartBox v-if="deformity" :spec="deformity.spec" :height="280" />
        </StatCard>
        <StatCard stat="fruits" :title="t.cards.fruits.title" :subtitle="t.cards.fruits.subtitle" :result="results.fruits" :unit="t.dashboard.fruitsUnit" :badges="fruits?.badges" :steps="fruits?.spec.steps" :refreshing="refreshing" shape="hbars" span="side">
          <ChartBox v-if="fruits" :spec="fruits.spec" :height="220" />
        </StatCard>
      </div>
    </section>

    <section class="section" aria-labelledby="sec-trends">
      <header class="section-head">
        <h2 id="sec-trends">{{ t.dashboard.sections.trends.title }}</h2>
        <p>{{ t.dashboard.sections.trends.lead }}</p>
      </header>
      <div class="cards">
        <StatCard stat="growth-good" :title="t.cards.goodGrowth.title" :subtitle="t.cards.growth.subtitle" :result="results.growth" :unit="t.dashboard.fruitsUnit" :badges="growth?.badges" :steps="growth?.good.steps" :empty-text="t.cards.growth.insufficient" :refreshing="refreshing" shape="bars" span="half">
          <ChartBox v-if="growth" :spec="growth.good" :height="240" />
        </StatCard>
        <StatCard stat="growth-rotten" :title="t.cards.rottenGrowth.title" :subtitle="t.cards.growth.subtitle" :result="results.growth" :unit="t.dashboard.fruitsUnit" :badges="growth?.badges" :steps="growth?.rotten.steps" :empty-text="t.cards.growth.insufficient" :refreshing="refreshing" shape="bars" span="half">
          <ChartBox v-if="growth" :spec="growth.rotten" :height="240" />
        </StatCard>
        <StatCard stat="recurring" :title="t.cards.recurring.title" :subtitle="t.cards.recurring.subtitle" :result="results.recurring" :n="recurring?.n" :unit="t.dashboard.fruitsUnit" :badges="recurring?.badges" :steps="recurring?.spec.steps" :refreshing="refreshing" shape="bars">
          <template v-if="recurring">
            <div class="seg-tabs segmented small" role="radiogroup" :aria-label="t.cards.recurring.title">
              <label v-for="k in ['week', 'month', 'season']" :key="k" :class="{ active: recurringTab === k }">
                <input v-model="recurringTab" type="radio" name="recurring" :value="k" />
                <span>{{ t.cards.recurring.tabs[k] }}</span>
              </label>
            </div>
            <ChartBox :spec="recurring.spec" :empty="recurring.empty" :height="260" />
          </template>
        </StatCard>
      </div>
    </section>

    <section class="section" aria-labelledby="sec-distributions">
      <header class="section-head">
        <h2 id="sec-distributions">{{ t.dashboard.sections.distributions.title }}</h2>
        <p>{{ t.dashboard.sections.distributions.lead }}</p>
      </header>
      <div class="cards">
        <StatCard stat="gaussian" :title="t.cards.gaussian.title" :subtitle="t.cards.gaussian.subtitle" :result="results.gaussian" :unit="t.dashboard.fruitsUnit" :steps="gaussian?.steps" :refreshing="refreshing" shape="hist">
          <TransitionGroup v-if="gaussian" name="multi" tag="div" class="gauss-grid">
            <section v-for="item in gaussian.items" :key="item.key" class="gauss" :class="{ flagged: item.s.flagged }">
              <ChartBox :spec="item.specs?.hist ?? null" :empty="item.empty" :caption="item.key" :badges="item.badges" :height="210" />
              <ChartBox v-if="item.specs" :spec="item.specs.qq" :caption="t.cards.gaussian.qq" :height="170" />
            </section>
          </TransitionGroup>
        </StatCard>
      </div>
    </section>

    <section class="section" aria-labelledby="sec-forecast">
      <header class="section-head">
        <h2 id="sec-forecast">{{ t.dashboard.sections.forecast.title }}</h2>
        <p>{{ t.dashboard.sections.forecast.lead }}</p>
      </header>
      <div class="cards">
        <StatCard stat="forecast" :title="t.cards.forecast.title" :subtitle="t.cards.forecast.subtitle" :result="results.forecast" :unit="t.dashboard.fruitsUnit" :steps="forecast?.steps" :refreshing="refreshing" shape="multiples">
          <TransitionGroup v-if="forecast" name="multi" tag="div" class="multiples">
            <ChartBox v-for="item in forecast.items" :key="item.key" :spec="item.spec" :empty="item.empty" :caption="item.key" :badges="item.badges" :height="200" />
          </TransitionGroup>
        </StatCard>
      </div>
    </section>
  </section>
</template>
