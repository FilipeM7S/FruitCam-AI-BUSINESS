<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { auth, logout } from "./auth.js";
import BrandLogo from "./components/BrandLogo.vue";
import GuideDialog from "./components/GuideDialog.vue";
import { motion, reducedMotion, setMotion, setTheme, theme } from "./media.js";
import { commands, panel, viewTransitions } from "./control.js";
import { t } from "./strings.js";

const FruitInspector = defineAsyncComponent(() => import("./components/FruitInspector.vue"));
const CommandBar = defineAsyncComponent(() => import("./components/CommandBar.vue"));
const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const vt = viewTransitions();
const router = useRouter();
const route = useRoute();

const NAV = [
  {
    group: t.app.navGroups.operation,
    items: [
      { to: "/", accent: "teal", long: t.app.navLine, short: t.app.navLine, icon: "M2 16h20M5 16a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm14 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM6 12h4v4H6zM13 9h5v7h-5zM11 3v3" },
      { to: "/inspecao", accent: "cashew", long: t.app.navAnalyze, short: t.app.navInspect, icon: "M4 8h3l2-3h6l2 3h3v11H4zM12 10a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" },
    ],
  },
  {
    group: t.app.navGroups.analysis,
    items: [
      { to: "/painel", accent: "gold", long: t.app.navDashboard, short: t.app.navDashboard, icon: "M3 20h18M6 20v-7M11 20V5M16 20v-10M21 20v-4" },
      { to: "/historico", accent: "sky", long: t.app.navHistory, short: t.app.navHistory, icon: "M4 6h16M4 12h16M4 18h10M3 6h.01M3 12h.01M3 18h.01" },
    ],
  },
  {
    group: t.app.navGroups.about,
    items: [
      { to: "/como-funciona", accent: "tan", long: t.app.navHow, short: t.app.navHowShort, icon: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v6M12 7.5v.01" },
      { to: "/creditos", accent: "sky", long: t.app.navCredits, short: t.app.navCreditsShort, icon: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM14.8 9.6a3.6 3.6 0 1 0 0 4.8" },
    ],
  },
];

const showTop = computed(() => Boolean(auth.user) || (route.meta.public && route.path !== "/login"));

watch(
  () => auth.checked,
  (checked) => {
    const boot = checked && document.getElementById("boot");
    if (!boot) return;
    if (reducedMotion()) return boot.remove();
    boot.addEventListener("transitionend", () => boot.remove(), { once: true });
    boot.classList.add("done");
  },
  { immediate: true },
);

function onKey(e) {
  if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "k" && auth.user) {
    e.preventDefault();
    commands.open = !commands.open;
  }
}

onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));

async function signOut() {
  await logout();
  router.push("/login");
}
</script>

<template>
  <a class="skip" href="#main">{{ t.app.skip }}</a>
  <div class="app" :class="{ shell: auth.user }" :data-accent="route.meta.accent || 'teal'">
    <header v-if="showTop" class="topbar">
      <div class="topbar-inner">
        <RouterLink to="/" class="brand" :aria-label="t.brand.home">
          <BrandLogo :height="40" />
        </RouterLink>
        <button v-if="auth.user" class="cmd-btn" type="button" :aria-label="`${t.control.commands.open} (${mac ? 'Cmd' : 'Ctrl'}+K)`" aria-keyshortcuts="Control+K Meta+K" @click="commands.open = true">
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></svg>
          <span class="cmd-label">{{ t.control.commands.open }}</span>
          <kbd class="cmd-kbd" aria-hidden="true">{{ mac ? "⌘" : "Ctrl" }} K</kbd>
        </button>
        <div class="topbar-tools" role="group" :aria-label="t.app.display">
          <button class="icon-btn" type="button" :aria-label="theme.dark ? t.theme.toLight : t.theme.toDark" :title="theme.dark ? t.theme.toLight : t.theme.toDark" @click="setTheme(!theme.dark)">
            <svg v-if="theme.dark" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
            <svg v-else width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" /></svg>
          </button>
          <button class="icon-btn motion-btn" type="button" :aria-pressed="motion.reduced" :aria-label="t.motion.reduce" :title="t.motion.reduce" @click="setMotion(!motion.reduced)">
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M3 8c3-3 6 3 9 0s6 3 9 0M3 16c3-3 6 3 9 0s6 3 9 0" /><path v-if="motion.reduced" d="M4 4l16 16" /></svg>
          </button>
        </div>
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
        <RouterLink v-for="item in g.items" :key="item.to" :to="item.to" :data-accent="item.accent">
          <svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path :d="item.icon" /></svg>
          <span class="nav-long">{{ item.long }}</span><span class="nav-short">{{ item.short }}</span>
        </RouterLink>
      </div>
    </nav>
    <main id="main" tabindex="-1">
      <RouterView v-slot="{ Component, route: r }">
        <Transition :name="vt ? 'none' : 'route'" :css="!vt" :mode="vt ? undefined : 'out-in'">
          <component :is="Component" :key="r.path" />
        </Transition>
      </RouterView>
    </main>
    <footer class="site-footer" :aria-label="t.footer.label">
      <div class="footer-inner">
        <BrandLogo :height="40" on="dark" />
        <nav class="footer-nav" :aria-label="t.footer.label">
          <RouterLink to="/como-funciona">{{ t.footer.how }}</RouterLink>
          <RouterLink to="/creditos">{{ t.footer.credits }}</RouterLink>
        </nav>
        <p class="footer-note">{{ t.footer.honesty }}</p>
      </div>
    </footer>
    <GuideDialog />
    <FruitInspector v-if="panel.mode" />
    <CommandBar v-if="commands.open" />
  </div>
</template>
