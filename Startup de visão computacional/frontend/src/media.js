import { reactive } from "vue";
import brand from "./brand.json";
import media from "./media.json";

const BASE = import.meta.env.BASE_URL;

export const theme = reactive({ dark: true });

export const BRAND = brand;

export function logoAsset(kind, surface) {
  if (kind === "icon") return brand.icon;
  return surface === "dark" ? brand.lockupOnDark : brand.lockupOnLight;
}

export function minHeight(kind) {
  const asset = logoAsset(kind, "light");
  const ink = kind === "icon" ? asset.height : asset.inkHeight;
  return Math.ceil((brand.rules.minInkHeightPx[kind] * asset.height) / ink);
}

export function url(path) {
  return `${BASE}${path.replace(/^\//, "")}`;
}

export function mediaItem(id) {
  return media.items[id];
}

export function srcset(item, format) {
  return item.sources[format].map(([w, path]) => `${url(path)} ${w}w`).join(", ");
}

export function credits(ids) {
  const seen = new Set();
  return ids
    .map((id) => media.items[id])
    .filter((m) => m && !seen.has(m.asset) && seen.add(m.asset))
    .map((m) => ({ asset: m.asset, credit: m.credit }));
}

export function reducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function constrainedData() {
  const c = typeof navigator !== "undefined" ? navigator.connection : null;
  return !!c && (c.saveData || ["slow-2g", "2g", "3g"].includes(c.effectiveType));
}

export const vReveal = {
  mounted(el) {
    el.classList.add("reveal");
    if (reducedMotion() || !("IntersectionObserver" in window)) {
      el.classList.add("revealed");
      return;
    }
    el._revealObserver = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      el.classList.add("revealed");
      el._revealObserver.disconnect();
    }, { rootMargin: "0px 0px -10% 0px" });
    el._revealObserver.observe(el);
  },
  unmounted(el) {
    el._revealObserver?.disconnect();
  },
};
