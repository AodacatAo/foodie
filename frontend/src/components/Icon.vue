<template>
  <svg
    class="icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="stroke"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    v-html="ICONS[name] || ''"
  ></svg>
</template>

<script setup>
// 统一的内联 SVG 图标（stroke 风格）：跨端渲染一致，替代 emoji
const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 },
  stroke: { type: [Number, String], default: 1.9 },
})

const ICONS = {
  bowl: '<path d="M3 11h18a9 9 0 0 1-18 0Z"/><path d="M9 7c0-1.6 1.2-2.2 1.2-3.8M13.4 7c0-1.6 1.2-2.2 1.2-3.8"/>',
  menu: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4v3h6V4"/><path d="M9 11h6M9 15h6M9 19h3"/>',
  import: '<path d="M12 3v10M8 9l4 4 4-4"/><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
  draft: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  settings: '<circle cx="12" cy="12" r="3.4"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.2 5.2l1.8 1.8M17 17l1.8 1.8M18.8 5.2 17 7M7 17l-1.8 1.8"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>',
  qr: '<rect x="3" y="3" width="7" height="7" rx="1.2"/><rect x="14" y="3" width="7" height="7" rx="1.2"/><rect x="3" y="14" width="7" height="7" rx="1.2"/><path d="M14 14h3.5v3.5H14zM20.5 17.5v3.5M14 20.5h2"/>',
  printer: '<path d="M7 8V4h10v4"/><rect x="3" y="8" width="18" height="8.5" rx="2"/><path d="M7 13.5h10v6.5H7z"/><path d="M16.5 11h.5"/>',
  cart: '<path d="M3 4h2l2.7 12.3a1 1 0 0 0 1 .7h9.6a1 1 0 0 0 1-.7L21 8H6"/><circle cx="9.5" cy="20" r="1.5"/><circle cx="17" cy="20" r="1.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  heart: '<path d="M12 20s-7-4.6-9.4-9A5.4 5.4 0 0 1 12 6.3 5.4 5.4 0 0 1 21.4 11c-2.4 4.4-9.4 9-9.4 9Z"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 6.5"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  back: '<path d="M15 5l-7 7 7 7"/>',
  edit: '<path d="M4 20h4L19 9l-3-3L5 17v3Z"/><path d="m14.5 6.5 3 3"/>',
  trash: '<path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
  share: '<path d="M12 15V4M8 8l4-4 4 4"/><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  servings: '<circle cx="8.5" cy="8.5" r="3"/><path d="M2.5 19c1-3 3.4-4.5 6-4.5s5 1.5 6 4.5"/><path d="M16.5 6a3 3 0 0 1 0 5M16 14.5c2.2.4 3.8 1.9 4.5 4.5"/>',
  wifi: '<path d="M4 9.5C7.5 6.2 16.5 6.2 20 9.5M7 13c2.4-2.2 7.6-2.2 10 0M9.8 16.2a3.4 3.4 0 0 1 4.4 0"/><circle cx="12" cy="19.5" r="1.2" fill="currentColor" stroke="none"/>',
}
</script>

<style scoped>
.icon { display: inline-block; vertical-align: -0.12em; flex: none; }
</style>
