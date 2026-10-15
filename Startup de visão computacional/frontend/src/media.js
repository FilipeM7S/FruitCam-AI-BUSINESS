import { reactive } from "vue";
import brand from "./brand.json";
import media from "./media.json";

const BASE = import.meta.env.BASE_URL;

const root = typeof document !== "undefined" ? document.documentElement : null;

export const theme = reactive({ dark: root?.dataset.theme !== "light" });

export const motion = reactive({ reduced: root?.dataset.motion === "reduced" });

function remember(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    return;
  }
}

export function setTheme(dark) {
  theme.dark = dark;
  if (dark) delete root.dataset.theme;
  else root.dataset.theme = "light";
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", getComputedStyle(root).getPropertyValue("--bg").trim());
  remember("fruitcam-theme", dark ? "dark" : "light");
}

export function setMotion(reduced) {
  motion.reduced = reduced;
  if (reduced) root.dataset.motion = "reduced";
  else delete root.dataset.motion;
  remember("fruitcam-motion", reduced ? "reduced" : "full");
}

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

export function reducedMotion() {
  return motion.reduced || (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
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
