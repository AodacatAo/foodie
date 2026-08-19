<template>
  <div>
    <div class="head">
      <div>
        <h1>🍽 餐厅库</h1>
        <p class="muted">{{ items.length }} 家店 · 距当前位置排序筛选</p>
      </div>
      <router-link to="/restaurant/new" class="btn-add">＋ 录入餐厅</router-link>
    </div>

    <!-- 位置栏（盒马式：只显示名称标签，不显示坐标） -->
    <div class="card pos-bar">
      <button class="secondary" :disabled="locating" @click="locate">
        📍 {{ locating ? '定位中…' : (pos ? '重新定位' : '自动定位') }}
      </button>
      <select v-model="posSelect" class="pos-select" @change="useSavedPos">
        <option value="">常用位置…</option>
        <option v-for="l in locations" :key="l.id" :value="l.id">{{ l.name }}</option>
      </select>
      <span class="pos-label" :class="{ unset: !pos }">
        {{ pos ? `📍 ${pos.label}` : '📍 未定位（点击左侧自动定位）' }}
      </span>
      <span v-if="pos" class="muted">
        <button class="ghost" @click="saveAsLocation">存为常用位置</button>
      </span>
      <span class="pos-advanced">
        <button class="ghost" @click="showManual = !showManual">{{ showManual ? '收起坐标' : '手动坐标' }}</button>
        <template v-if="showManual">
          <input v-model.number="manualLat" class="coord" placeholder="纬度" />
          <input v-model.number="manualLng" class="coord" placeholder="经度" />
          <button class="secondary" @click="useManualPos">确定</button>
        </template>
      </span>
    </div>

    <!-- 筛选栏 -->
    <div class="card filters">
      <input v-model="searchText" class="search" placeholder="🔍 搜店名 / 菜系 / 地址…" @input="onSearchInput" />
      <select v-model="f.cuisine">
        <option value="">全部菜系</option>
        <option v-for="c in cuisines" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="f.maxPrice">
        <option value="">人均不限</option>
        <option v-for="p in [50, 100, 150, 200, 300]" :key="p" :value="p">人均 ≤ {{ p }} 元</option>
      </select>
      <select v-model="f.minRating">
        <option value="">我的评分不限</option>
        <option value="3">我的分 ≥ 3</option>
        <option value="4">我的分 ≥ 4</option>
        <option value="4.5">我的分 ≥ 4.5</option>
      </select>
      <select v-model="f.eaten">
        <option value="">吃过/没吃过</option>
        <option value="all">全部</option>
        <option value="eaten">吃过</option>
        <option value="not">没吃过</option>
      </select>
      <select v-model="f.maxDist">
        <option value="">距离不限</option>
        <option value="3">3 km 内</option>
        <option value="5">5 km 内</option>
        <option value="10">10 km 内</option>
        <option value="20">20 km 内</option>
      </select>
      <select v-model="sortBy" class="sort">
        <option value="distance">排序：距离最近</option>
        <option value="price">排序：人均从低到高</option>
        <option value="myRating">排序：我的评分最高</option>
        <option value="recent">排序：最近吃过</option>
        <option value="count">排序：吃过次数最多</option>
      </select>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-else-if="loading && !items.length" class="empty">加载中…</div>
    <div v-else-if="!sorted.length" class="empty">
      {{ items.length ? '没有符合筛选条件的餐厅' : '还没有餐厅，点「＋ 录入餐厅」添加第一家吧' }}
    </div>

    <div class="grid" v-else>
      <router-link
        v-for="r in sorted" :key="r.id"
        :to="`/restaurant/${r.id}`" class="card shop-card"
      >
        <div class="cover">
          <img v-if="r.cover_image" :src="mediaUrl(r.cover_image)" alt="" loading="lazy" decoding="async" />
          <span v-else class="cover-fallback">🍽</span>
          <span v-if="r.status === 'draft'" class="draft-badge">草稿</span>
          <button
            class="plus-one"
            :class="{ done: plusDone === r.id }"
            title="记录一次用餐（可进详情补充照片/备注）"
            @click.stop.prevent="plusOne(r)"
          >{{ plusDone === r.id ? '✓' : '+1' }}</button>
        </div>
        <div class="body">
          <h3>{{ r.name }}</h3>
          <div class="meta">
            <span v-if="r.cuisine" class="tag">{{ r.cuisine }}</span>
            <span v-if="r.price_per_person" class="badge price">¥{{ r.price_per_person }}</span>
            <span v-if="distOf(r) !== null" class="badge">📍 {{ distOf(r) }} km</span>
            <span v-if="r.visit_count" class="badge eaten">🍽 吃过 {{ r.visit_count }} 次</span>
          </div>
          <div class="card-actions" @click.stop.prevent>
            <div class="my-rating">
              <span v-for="n in 5" :key="n" class="star-wrap" @click="rateHalf(r, n, $event)">
                <span class="star" :class="{ on: r.my_rating != null && n <= Math.floor(r.my_rating + 0.001) }">★</span>
                <span
                  v-if="r.my_rating != null && n === Math.floor(r.my_rating + 0.001) + 1 && r.my_rating % 1 >= 0.25"
                  class="star half"
                >★</span>
              </span>
              <input
                :value="r.my_rating == null ? '' : r.my_rating.toFixed(1)"
                class="rating-input"
                type="number" min="0" max="5" step="0.1"
                @change="rate(r, Number($event.target.value))"
              />
            </div>
          </div>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue'
import { api, mediaUrl } from '../api'

const items = ref([])
const locations = ref([])
const error = ref('')
const searchText = ref('')
const locating = ref(false)
const posSelect = ref('')
const manualLat = ref(null)
const manualLng = ref(null)
const pos = ref(loadPos())
const showManual = ref(false)
const f = ref({ cuisine: '', maxPrice: '', minRating: '', eaten: '', maxDist: '' })
const sortBy = ref('distance')
const loading = ref(false)
const plusDone = ref(null)

let debounceTimer = null

function loadPos() {
  try { return JSON.parse(localStorage.getItem('foodie_pos') || 'null') } catch { return null }
}
function savePos(p) {
  pos.value = p
  localStorage.setItem('foodie_pos', JSON.stringify(p))
}

function haversine(a, b) {
  const R = 6371
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const s = Math.sin(dLat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s))
}

const distOf = (r) => {
  if (!pos.value || r.lat == null || r.lng == null) return null
  return haversine(pos.value, { lat: r.lat, lng: r.lng }).toFixed(1)
}

const cuisines = computed(() => [...new Set(items.value.map((r) => r.cuisine).filter(Boolean))].sort())

const filtered = computed(() => items.value.filter((r) => {
  if (f.value.cuisine && r.cuisine !== f.value.cuisine) return false
  if (f.value.maxPrice && (r.price_per_person == null || r.price_per_person > Number(f.value.maxPrice))) return false
  if (f.value.minRating && (r.my_rating == null || r.my_rating < Number(f.value.minRating))) return false
  if (f.value.eaten === 'eaten' && !r.visit_count) return false
  if (f.value.eaten === 'not' && r.visit_count) return false
  const d = distOf(r)
  if (f.value.maxDist && (d === null || Number(d) > Number(f.value.maxDist))) return false
  return true
}))

const sorted = computed(() => {
  const arr = [...filtered.value]
  const key = {
    distance: (r) => (distOf(r) === null ? 1e9 : Number(distOf(r))),
    price: (r) => r.price_per_person ?? 1e9,
    myRating: (r) => -(r.my_rating ?? -1),
    recent: (r) => -(r.last_visited_at ? new Date(r.last_visited_at).getTime() : 0),
    count: (r) => -(r.visit_count ?? 0),
  }[sortBy.value]
  arr.sort((a, b) => key(a) - key(b))
  return arr
})

async function load() {
  error.value = ''
  loading.value = true
  try {
    const params = { page_size: 1000 }
    if (searchText.value) params.q = searchText.value
    const data = await api.listRestaurants(params)
    items.value = data.items
  } catch (e) { error.value = e.message } finally { loading.value = false }
}

async function loadLocations() {
  try { locations.value = await api.listLocations() } catch { /* ignore */ }
}

function locate() {
  if (navigator.geolocation) {
    locating.value = true
    error.value = ''
    navigator.geolocation.getCurrentPosition(
      (p) => {
        savePos({ lat: p.coords.latitude, lng: p.coords.longitude, label: '我的位置', accuracy: p.coords.accuracy })
        locating.value = false
      },
      () => { locateByIp(false) },  // GPS 失败（如局域网 http 下被浏览器禁用）→ 网络定位兜底
      { enableHighAccuracy: true, timeout: 10000 },
    )
  } else {
    locateByIp(false)
  }
}

// 网络定位兜底：局域网 http 访问时浏览器禁用 GPS，改按出口 IP 估算位置（大致到街道级别）
async function locateByIp(silent = false) {
  locating.value = true
  if (!silent) error.value = ''
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
        savePos({ lat: p.lat, lng: p.lng, label: '网络定位（近似）' })
        locating.value = false
        return
      }
    } catch { /* 尝试下一个源 */ }
  }
  locating.value = false
  if (!silent) error.value = '定位失败：请点「📍 自动定位」重试，或选择常用位置 / 手动输入坐标'
}

function useSavedPos() {
  const loc = locations.value.find((l) => String(l.id) === String(posSelect.value))
  if (loc) savePos({ lat: loc.lat, lng: loc.lng, label: loc.name })
}

function useManualPos() {
  if (manualLat.value == null || manualLng.value == null) { error.value = '请输入纬度和经度'; return }
  savePos({ lat: manualLat.value, lng: manualLng.value, label: '手动位置' })
}

async function saveAsLocation() {
  if (!pos.value) return
  const name = prompt('给这个位置起个名字（如：家 / 公司）：')
  if (!name) return
  try {
    await api.createLocation({ name: name.trim(), lat: pos.value.lat, lng: pos.value.lng })
    await loadLocations()
  } catch (e) { error.value = e.message }
}

function onSearchInput() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(load, 300)
}

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

async function plusOne(r) {
  try {
    await api.addVisit(r.id, { visited_at: todayStr(), note: null, photos: [] })
    r.visit_count = (r.visit_count || 0) + 1
    r.last_visited_at = new Date().toISOString()
    plusDone.value = r.id
    setTimeout(() => { if (plusDone.value === r.id) plusDone.value = null }, 1200)
  } catch (e) { error.value = e.message }
}

async function rate(r, val) {
  if (val == null || Number.isNaN(val)) { r.my_rating = null; await api.setMyRating(r.id, null); return }
  const v = Math.min(5, Math.max(0, Math.round(Number(val) * 10) / 10))
  r.my_rating = v
  try { await api.setMyRating(r.id, v) } catch (e) { error.value = e.message }
}

function rateHalf(r, n, e) {
  // 用 clientX 计算（触屏点击同样有效），左半颗=减 0.5
  const rect = e.currentTarget.getBoundingClientRect()
  const half = (e.clientX ?? e.offsetX) - rect.left < rect.width / 2
  rate(r, half ? n - 0.5 : n)
}

onMounted(() => {
  load()
  loadLocations()
  // 没有保存位置时自动尝试定位（静默失败，可手动；局域网 http 下 GPS 被禁用则网络定位兜底）
  if (!pos.value) {
    const autoLocate = () => {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (p) => savePos({ lat: p.coords.latitude, lng: p.coords.longitude, label: '我的位置', accuracy: p.coords.accuracy }),
          () => locateByIp(true),  // 静默兜底
          { enableHighAccuracy: true, timeout: 8000 },
        )
      } else {
        locateByIp(true)
      }
    }
    autoLocate()
  }
})
onBeforeUnmount(() => clearTimeout(debounceTimer))
watch(() => f.value.cuisine, () => {})
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 14px; }
.head h1 { font-size: 22px; }
.btn-add { background: #e5533c; color: #fff; text-decoration: none; padding: 8px 16px; border-radius: 8px; font-size: 14px; }
.pos-bar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; padding: 10px 16px; }
.pos-select { width: auto; }
.coord { width: 90px; display: inline-block; }
.pos-label { font-size: 14px; font-weight: 600; color: #e5533c; }
.pos-label.unset { color: #999; font-weight: 400; }
.pos-advanced { display: flex; gap: 6px; align-items: center; margin-left: auto; flex-wrap: wrap; }
.warn { color: #e5a000; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.filters select, .filters .search { width: auto; }
.search { max-width: 220px; }
.sort { margin-left: auto; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.shop-card { display: block; text-decoration: none; color: inherit; padding: 0; overflow: hidden; transition: transform 0.12s, box-shadow 0.12s; }
.shop-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); }
.shop-card:hover .cover img { transform: scale(1.06); }
.cover { position: relative; height: 130px; background: #f5efe8; display: flex; align-items: center; justify-content: center; }
.cover img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.35s ease; }
.cover-fallback { font-size: 36px; }
.draft-badge { position: absolute; top: 8px; left: 8px; background: #f5a623; color: #fff; font-size: 12px; border-radius: 10px; padding: 1px 8px; }
.plus-one {
  position: absolute; top: 8px; right: 8px;
  background: rgba(229, 83, 60, 0.92); color: #fff; border-radius: 8px;
  padding: 4px 12px; font-size: 13px; font-weight: 700; min-width: 40px;
}
.plus-one.done { background: #2e7d32; }
.plus-one:hover { background: #c9442e; }
.body { padding: 12px 14px; }
.body h3 { font-size: 15.5px; font-weight: 700; margin-bottom: 7px; color: #2f2a24; }
.meta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }
.card-actions { display: flex; align-items: center; gap: 6px; }
.price { color: var(--brand-deep); font-weight: 700; }
.eaten { background: #e8f5e9; color: #2e7d32; }
.my-rating { display: flex; align-items: center; gap: 2px; }
.star-wrap { position: relative; display: inline-block; font-size: 15px; cursor: pointer; user-select: none; line-height: 1; }
.star { color: #ddd; }
.star.on { color: #f5a623; }
.star.half { position: absolute; inset: 0; width: 50%; overflow: hidden; color: #f5a623; pointer-events: none; }
.rating-input { width: 44px; padding: 2px 4px; font-size: 12px; border-radius: 6px; }

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .head { flex-wrap: wrap; gap: 8px; }
  .btn-add { width: 100%; text-align: center; padding: 11px 16px; }
  .pos-advanced { margin-left: 0; }
  .pos-bar button.secondary { flex: none; }
  .filters { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .filters .search, .filters .sort { grid-column: 1 / -1; }
  .filters select, .filters .search { width: 100%; min-width: 0; }
  .sort { margin-left: 0; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .cover { height: 92px; }
  .cover-fallback { font-size: 28px; }
  .plus-one { padding: 5px 10px; min-width: 38px; font-size: 13px; }
  .body { padding: 8px 10px; }
  .body h3 { font-size: 14px; }
  .my-rating { flex-wrap: wrap; }
  .star-wrap { font-size: 16px; } /* 更大的触控热区 */
}
</style>
