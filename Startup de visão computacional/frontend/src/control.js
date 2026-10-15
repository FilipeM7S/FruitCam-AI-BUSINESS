import { nextTick, reactive } from "vue";
import { reducedMotion } from "./media.js";

export const panel = reactive({ mode: null, event: null, id: null, extra: null, drill: null, replay: null, from: null });
export const commands = reactive({ open: false });

function show(mode, fields, from) {
  const apply = () => Object.assign(panel, { mode, event: null, id: null, extra: null, drill: null, replay: null, from }, fields);
  const shot = mode !== "event" ? null : from?.querySelector?.("img, canvas") || (from?.matches?.("img, canvas") ? from : null);
  if (!shot || !document.startViewTransition || reducedMotion()) return apply();
  shot.style.viewTransitionName = "fruit-shot";
  document.startViewTransition(async () => {
    shot.style.viewTransitionName = "";
    apply();
    await nextTick();
  });
}

export const openEvent = (event, extra = null, from = null) => show("event", { event, id: event.id, extra }, from);
export const openEventId = (id, from = null) => show("event", { id }, from);
export const openDrill = (drill, from = null) => show("drill", { drill }, from);
export const openReplay = (replay, from = null) => show("replay", { replay }, from);

export function closePanel() {
  const back = panel.from;
  panel.mode = null;
  nextTick(() => back?.focus?.());
}

let tip = null;
let tipFor = null;
let hideTimer = 0;

function tipEl() {
  if (tip) return tip;
  tip = Object.assign(document.createElement("div"), { id: "trace-tip", className: "trace-tip", hidden: true });
  tip.setAttribute("role", "tooltip");
  tip.addEventListener("mouseenter", () => clearTimeout(hideTimer));
  tip.addEventListener("mouseleave", hideTip);
  document.body.append(tip);
  document.addEventListener("keydown", (e) => e.key === "Escape" && hideTip(true));
  return tip;
}

function showTip(el) {
  clearTimeout(hideTimer);
  const t = tipEl();
  tipFor?.removeAttribute("aria-describedby");
  tipFor = el;
  t.textContent = el.dataset.trace;
  t.hidden = false;
  el.setAttribute("aria-describedby", "trace-tip");
  const r = el.getBoundingClientRect();
  const w = t.offsetWidth;
  const h = t.offsetHeight;
  const below = r.bottom + 8 + h < innerHeight;
  t.style.left = `${Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2))}px`;
  t.style.top = `${below ? r.bottom + 8 : Math.max(8, r.top - h - 8)}px`;
}

function hideTip(now) {
  clearTimeout(hideTimer);
  const go = () => {
    if (tip) tip.hidden = true;
    tipFor?.removeAttribute("aria-describedby");
    tipFor = null;
  };
  if (now === true) return go();
  hideTimer = setTimeout(go, 150);
}

function attach(el) {
  el.classList.add("traced");
  if (el.tabIndex < 0) el.tabIndex = 0;
  el._trace = [["mouseenter", () => showTip(el)], ["focus", () => showTip(el)], ["mouseleave", hideTip], ["blur", () => hideTip(true)]];
  el._trace.forEach(([k, f]) => el.addEventListener(k, f));
}

export const vTrace = {
  mounted(el, binding) {
    if (!binding.value) return;
    el.dataset.trace = binding.value;
    attach(el);
  },
  updated(el, binding) {
    if (!binding.value) return;
    el.dataset.trace = binding.value;
    if (!el._trace) attach(el);
    if (tipFor === el && tip) tip.textContent = el.dataset.trace;
  },
  unmounted(el) {
    el._trace?.forEach(([k, f]) => el.removeEventListener(k, f));
    if (tipFor === el) hideTip(true);
  },
};

export function tween(from, to, ms, set) {
  if (reducedMotion() || from === to || !Number.isFinite(from) || !Number.isFinite(to)) {
    set(to);
    return () => {};
  }
  const t0 = performance.now();
  let raf = requestAnimationFrame(function step(now) {
    const k = Math.min(1, (now - t0) / ms);
    set(k < 1 ? from + (to - from) * (1 - Math.pow(1 - k, 3)) : to);
    if (k < 1) raf = requestAnimationFrame(step);
  });
  return () => cancelAnimationFrame(raf);
}

export const vMagnetic = {
  mounted(el) {
    const fine = window.matchMedia("(pointer: fine)").matches;
    if (!fine) return;
    el._magnet = [
      ["pointermove", (e) => {
        if (reducedMotion() || el.disabled) return;
        const r = el.getBoundingClientRect();
        const dx = ((e.clientX - r.left) / r.width - 0.5) * 6;
        const dy = ((e.clientY - r.top) / r.height - 0.5) * 4;
        el.style.transform = `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px)`;
      }],
      ["pointerleave", () => (el.style.transform = "")],
    ];
    el._magnet.forEach(([k, f]) => el.addEventListener(k, f));
    el.classList.add("magnetic");
  },
  unmounted(el) {
    el._magnet?.forEach(([k, f]) => el.removeEventListener(k, f));
  },
};

export function routeTransitions(router) {
  let finish = null;
  router.beforeResolve((to, from) => {
    if (!document.startViewTransition || reducedMotion() || to.path === from.path || !from.matched.length) return;
    return new Promise((resolve) => {
      document.startViewTransition(() => new Promise((done) => {
        finish = done;
        resolve();
      }));
    });
  });
  router.afterEach(async () => {
    if (!finish) return;
    await nextTick();
    finish();
    finish = null;
  });
  router.onError(() => {
    finish?.();
    finish = null;
  });
}

export const viewTransitions = () => typeof document !== "undefined" && Boolean(document.startViewTransition) && !reducedMotion();
