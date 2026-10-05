<script setup>
import { t } from "../strings.js";

const LINE = 470;
const fruits = [
  { cls: "boa", y: 214, rx: 21, ry: 15, x: 120, delay: -0.5 },
  { cls: "podre", y: 246, rx: 19, ry: 14, x: 250, delay: -2.6 },
  { cls: "poor", y: 200, rx: 15, ry: 11, x: 375, delay: -4.4 },
  { cls: "boa", y: 238, rx: 22, ry: 15, x: 540, delay: -6.1 },
  { cls: "poor", y: 222, rx: 16, ry: 12, x: 640, delay: -7.6 },
];
const labels = { boa: "boa", poor: "baixa qual.", podre: "podre" };
</script>

<template>
  <figure class="cam-diagram">
    <svg viewBox="0 0 760 330" role="img" :aria-label="t.line.diagramAlt">
      <defs>
        <linearGradient id="cam-fov" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#9ad9b3" stop-opacity="0.32" />
          <stop offset="1" stop-color="#9ad9b3" stop-opacity="0.04" />
        </linearGradient>
        <clipPath id="cam-belt-clip"><rect x="64" y="176" width="632" height="96" /></clipPath>
      </defs>
      <polygon points="300,78 460,78 690,176 70,176" fill="url(#cam-fov)" />
      <line x1="300" y1="78" x2="70" y2="176" class="cam-fov-edge" />
      <line x1="460" y1="78" x2="690" y2="176" class="cam-fov-edge" />
      <rect x="110" y="34" width="120" height="12" rx="6" class="cam-light" />
      <rect x="530" y="34" width="120" height="12" rx="6" class="cam-light" />
      <text x="170" y="26" class="cam-label" text-anchor="middle">{{ t.line.diagram.light }}</text>
      <text x="590" y="26" class="cam-label" text-anchor="middle">{{ t.line.diagram.light }}</text>
      <rect x="326" y="22" width="108" height="56" rx="10" class="cam-body" />
      <circle cx="380" cy="64" r="16" class="cam-lens" />
      <circle cx="380" cy="64" r="7" class="cam-lens-in" />
      <text x="380" y="14" class="cam-label strong" text-anchor="middle">{{ t.line.diagram.camera }}</text>
      <text x="606" y="132" class="cam-label">{{ t.line.diagram.view }}</text>
      <circle cx="48" cy="224" r="48" class="cam-roller" />
      <circle cx="712" cy="224" r="48" class="cam-roller" />
      <rect x="48" y="176" width="664" height="96" class="cam-belt" />
      <g clip-path="url(#cam-belt-clip)">
        <g v-for="(f, i) in fruits" :key="i" class="cam-fruit" :class="{ past: f.x > LINE }" :style="{ transform: `translateX(${f.x}px)`, animationDelay: `${f.delay}s` }">
          <ellipse :cx="0" :cy="f.y" :rx="f.rx" :ry="f.ry" :class="`fruit-${f.cls}`" />
          <rect :x="-f.rx - 6" :y="f.y - f.ry - 6" :width="2 * f.rx + 12" :height="2 * f.ry + 12" rx="3" class="cam-track" :style="{ animationDelay: `${f.delay}s` }" />
          <g class="cam-tag" :class="`tag-${f.cls}`" :style="{ animationDelay: `${f.delay}s` }">
            <rect :x="-f.rx - 6" :y="f.y - f.ry - 6" :width="2 * f.rx + 12" :height="2 * f.ry + 12" rx="3" />
            <text :x="-f.rx - 6" :y="f.y - f.ry - 11">{{ labels[f.cls] }}</text>
          </g>
        </g>
      </g>
      <line :x1="LINE" y1="160" :x2="LINE" y2="290" class="cam-count" />
      <text :x="LINE" y="306" class="cam-label strong" text-anchor="middle">{{ t.line.diagram.line }}</text>
      <text x="60" y="306" class="cam-label">{{ t.line.diagram.belt }}</text>
      <path d="M560 302 h96" class="cam-arrow" />
      <path d="M648 296 l10 6 -10 6" class="cam-arrow-head" />
      <text x="608" y="324" class="cam-label" text-anchor="middle">{{ t.line.diagram.direction }}</text>
    </svg>
  </figure>
</template>
