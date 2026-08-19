<template>
  <div>
    <h1 class="page-title">⚙️ 设置</h1>

    <div class="card">
      <h2>📍 常用位置</h2>
      <p class="muted">保存家/公司等固定位置，餐厅列表可一键选为当前位置计算距离。</p>
      <div class="loc-row">
        <input v-model="loc.name" placeholder="名称（如：家）" class="loc-name" />
        <button class="secondary" :disabled="locating" @click="useCurrent">
          {{ locating ? '定位中…' : '📍 用当前定位' }}
        </button>
        <input v-model.number="loc.lat" placeholder="纬度" class="loc-coord" />
        <input v-model.number="loc.lng" placeholder="经度" class="loc-coord" />
        <button :disabled="saving" @click="add">＋ 添加</button>
      </div>
      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="!locations.length" class="muted empty">还没有常用位置</div>
      <div v-for="l in locations" :key="l.id" class="loc-item">
        <b>{{ l.name }}</b>
        <span class="muted">{{ l.lat.toFixed(5) }}, {{ l.lng.toFixed(5) }}</span>
        <button class="ghost" :class="{ confirming: confirmDel === l.id }" @click="askDelete(l)">
          {{ confirmDel === l.id ? '再点确认' : '✕' }}
        </button>
      </div>
    </div>

    <div class="card">
      <h2>📶 局域网访问</h2>
      <p class="muted">手机 / 平板连同一个 Wi-Fi 打开下面地址即可，<b>免登录</b>（外网访问才需要密码，登录一次管一年）。自动定位可能被浏览器禁用，可用常用位置或手动坐标。</p>
      <div v-if="net.ips.length" class="lan-ips">
        <div v-for="ip in net.ips" :key="ip" class="lan-row">
          <code>http://{{ ip }}:{{ net.port }}</code>
          <button class="secondary small" @click="copyIp(ip, net.port)">复制</button>
        </div>
      </div>
      <p v-else class="muted">正在获取局域网地址…</p>
      <p class="muted">当前打开地址：<code>{{ locationHost }}</code></p>
    </div>

    <div class="card">
      <h2>ℹ️ 关于</h2>
      <p class="muted">食集 · 本地美食库。菜谱 + 餐厅收藏，数据全部存在本机（backend/data/），备份：<code>./scripts/backup.sh</code></p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const locations = ref([])
const saving = ref(false)
const locating = ref(false)
const error = ref('')
const loc = ref({ name: '', lat: null, lng: null })
const net = ref({ ips: [], port: 8080 })
const locationHost = ref(window.location.host)

async function loadNet() {
  try {
    const data = await api.netInfo()
    net.value = data
  } catch { /* 忽略 */ }
}

async function copyIp(ip, port) {
  try {
    await navigator.clipboard.writeText(`http://${ip}:${port}`)
    error.value = ''
  } catch {
    error.value = '复制失败，请手动输入'
  }
}

function useCurrent() {
  locating.value = true
  error.value = ''
  const apply = (lat, lng) => {
    loc.value.lat = Math.round(lat * 1e6) / 1e6
    loc.value.lng = Math.round(lng * 1e6) / 1e6
    locating.value = false
  }
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (p) => apply(p.coords.latitude, p.coords.longitude),
      () => useCurrentByIp(apply),  // GPS 失败 → 网络定位兜底
      { enableHighAccuracy: true, timeout: 10000 },
    )
  } else {
    useCurrentByIp(apply)  // 局域网 http 下 GPS 被禁用
  }
}

// 按出口 IP 估算位置（到街道级别）
async function useCurrentByIp(apply) {
  const sources = [
    {
      url: 'https://ipinfo.io/json',
      parse: (j) => {
        if (!j || !j.loc) return null
        const [lat, lng] = String(j.loc).split(',').map(Number)
        return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null
      },
    },
    {
      url: 'http://ip-api.com/json/?lang=zh-CN',
      parse: (j) => (j && j.status === 'success' ? { lat: j.lat, lng: j.lon } : null),
    },
  ]
  for (const src of sources) {
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 6000)
      const res = await fetch(src.url, { signal: ctrl.signal })
      clearTimeout(timer)
      if (!res.ok) continue
      const p = src.parse(await res.json())
      if (p && Number.isFinite(p.lat) && Number.isFinite(p.lng)) {
        apply(p.lat, p.lng)
        return
      }
    } catch { /* 尝试下一个源 */ }
  }
  locating.value = false
  error.value = '定位失败：可手动输入坐标'
}

async function load() {
  try { locations.value = await api.listLocations() } catch (e) { error.value = e.message }
}

async function add() {
  if (!loc.value.name.trim() || loc.value.lat == null || loc.value.lng == null) {
    error.value = '请填写名称、纬度和经度'
    return
  }
  saving.value = true
  error.value = ''
  try {
    await api.createLocation({ name: loc.value.name.trim(), lat: loc.value.lat, lng: loc.value.lng })
    loc.value = { name: '', lat: null, lng: null }
    await load()
  } catch (e) { error.value = e.message } finally { saving.value = false }
}

async function remove(l) {
  try { await api.deleteLocation(l.id); await load() } catch (e) { error.value = e.message }
}

const confirmDel = ref(null)
let confirmTimer = null
function askDelete(l) {
  if (confirmDel.value === l.id) {
    confirmDel.value = null
    clearTimeout(confirmTimer)
    remove(l)
    return
  }
  confirmDel.value = l.id
  clearTimeout(confirmTimer)
  confirmTimer = setTimeout(() => { confirmDel.value = null }, 3000)
}

onMounted(() => {
  load()
  loadNet()
})
</script>

<style scoped>
.page-title { font-size: 22px; margin-bottom: 14px; }
.card { margin-bottom: 14px; }
.card h2 { font-size: 17px; margin-bottom: 8px; color: #e5533c; }
.loc-row { display: flex; gap: 8px; margin: 10px 0; }
.loc-name { flex: 1; }
.loc-coord { width: 120px; }
.loc-item { display: flex; gap: 10px; align-items: center; padding: 8px 0; border-bottom: 1px dashed #eee; }
.empty { padding: 8px 0; }
.error { margin-top: 8px; }
.lan-ips { display: flex; flex-direction: column; gap: 8px; margin: 10px 0; }
.lan-row { display: flex; align-items: center; gap: 10px; }
.lan-row code { background: #f5f1ea; padding: 6px 10px; border-radius: 8px; font-size: 14px; }
button.small { padding: 4px 12px; font-size: 12px; }

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .loc-row { flex-wrap: wrap; }
  .loc-name { flex: 1 1 100%; }
  .loc-coord { flex: 1; min-width: 90px; }
}
</style>
