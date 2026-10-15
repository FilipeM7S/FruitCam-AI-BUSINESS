import { createRouter, createWebHistory } from "vue-router";
import { auth, loadUser } from "./auth.js";
import { routeTransitions } from "./control.js";
import { reducedMotion } from "./media.js";
import LoginView from "./views/LoginView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginView, meta: { public: true, accent: "teal" } },
    { path: "/", component: () => import("./views/LineView.vue"), meta: { accent: "teal" } },
    { path: "/inspecao", component: () => import("./views/UploadView.vue"), meta: { accent: "cashew" } },
    { path: "/painel", component: () => import("./views/DashboardView.vue"), meta: { accent: "gold" } },
    { path: "/historico", component: () => import("./views/HistoryView.vue"), meta: { accent: "sky" } },
    { path: "/como-funciona", component: () => import("./views/HowItWorksView.vue"), meta: { public: true, accent: "tan" } },
    { path: "/creditos", component: () => import("./views/CreditsView.vue"), meta: { public: true, accent: "sky" } },
    { path: "/:rest(.*)", redirect: "/" },
  ],
  scrollBehavior(to, from, saved) {
    if (saved) return saved;
    if (to.hash) return { el: to.hash, top: 80, behavior: reducedMotion() ? "auto" : "smooth" };
    return { top: 0 };
  },
});

routeTransitions(router);

router.beforeEach(async (to) => {
  if (!auth.checked) await loadUser();
  if (!to.meta.public && !auth.user) return { path: "/login", query: { next: to.fullPath } };
  if (to.path === "/login" && auth.user) return "/";
});
