<script setup>
import { computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { auth, logout } from "./auth.js";
import BrandLogo from "./components/BrandLogo.vue";
import GuideDialog from "./components/GuideDialog.vue";
import { t } from "./strings.js";

const router = useRouter();
const route = useRoute();

const NAV = [
  {
    group: t.app.navGroups.operation,
    items: [
      { to: "/", long: t.app.navLine, short: t.app.navLine, icon: "M2 16h20M5 16a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm14 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM6 12h4v4H6zM13 9h5v7h-5zM11 3v3" },
      { to: "/inspecao", long: t.app.navAnalyze, short: t.app.navInspect, icon: "M4 8h3l2-3h6l2 3h3v11H4zM12 10a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" },
    ],
  },
  {
    group: t.app.navGroups.analysis,
    items: [{ to: "/painel", long: t.app.navDashboard, short: t.app.navDashboard, icon: "M3 20h18M6 20v-7M11 20V5M16 20v-10M21 20v-4" }],
  },
  {
    group: t.app.navGroups.about,
    items: [
      { to: "/como-funciona", long: t.app.navHow, short: t.app.navHowShort, icon: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v6M12 7.5v.01" },
      { to: "/creditos", long: t.app.navCredits, short: t.app.navCreditsShort, icon: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM14.8 9.6a3.6 3.6 0 1 0 0 4.8" },
    ],
  },
];

const showTop = computed(() => Boolean(auth.user) || (route.meta.public && route.path !== "/login"));

watch(
  () => auth.checked,
  (checked) => {
    const boot = checked && document.getElementById("boot");
    if (!boot) return;
    boot.addEventListener("transitionend", () => boot.remove(), { once: true });
    boot.classList.add("done");
  },
  { immediate: true },
);

async function signOut() {
  await logout();
  router.push("/login");
}
</script>

<template>
  <a class="skip" href="#main">{{ t.app.skip }}</a>
  <div class="app" :class="{ shell: auth.user }">
    <header v-if="showTop" class="topbar">
      <div class="topbar-inner">
        <RouterLink to="/" class="brand" :aria-label="t.brand.home">
          <BrandLogo :height="40" />
        </RouterLink>
        <div v-if="auth.user" class="user" role="group" :aria-label="t.app.account">
          <span class="user-name" :title="`${t.app.signedAs} ${auth.user.username}`">{{ auth.user.username }}</span>
          <button class="btn btn-ghost btn-sm" type="button" @click="signOut">{{ t.app.logout }}</button>
        </div>
        <RouterLink v-else class="btn btn-secondary btn-sm" :to="{ path: '/login', query: { next: route.fullPath } }">{{ t.app.login }}</RouterLink>
      </div>
    </header>
    <nav v-if="auth.user" class="nav" :aria-label="t.app.navLabel">
      <div v-for="g in NAV" :key="g.group" class="nav-group">
        <p class="nav-group-label">{{ g.group }}</p>
        <RouterLink v-for="item in g.items" :key="item.to" :to="item.to">
          <svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path :d="item.icon" /></svg>
          <span class="nav-long">{{ item.long }}</span><span class="nav-short">{{ item.short }}</span>
        </RouterLink>
      </div>
    </nav>
    <main id="main" tabindex="-1">
      <RouterView v-slot="{ Component, route: r }">
        <Transition name="route" mode="out-in">
          <component :is="Component" :key="r.path" />
        </Transition>
      </RouterView>
    </main>
    <footer class="site-footer" :aria-label="t.footer.label">
      <div class="footer-inner">
        <BrandLogo :height="40" />
        <nav class="footer-nav" :aria-label="t.footer.label">
          <RouterLink to="/como-funciona">{{ t.footer.how }}</RouterLink>
          <RouterLink to="/creditos">{{ t.footer.credits }}</RouterLink>
        </nav>
        <p class="footer-note">{{ t.footer.honesty }}</p>
      </div>
    </footer>
    <GuideDialog />
  </div>
</template>
