<template>
  <div v-if="error" class="error">{{ error }}</div>
  <div v-else-if="!shop" class="empty">加载中…</div>
  <template v-else>
    <button class="ghost back" @click="$router.push('/restaurants')">← 返回餐厅库</button>

    <div v-if="shop.status === 'draft'" class="draft-banner">
      ⚠️ 待确认的餐厅，核对信息后发布
      <div class="banner-actions">
        <button class="secondary" @click="editing = true">编辑</button>
        <button @click="publish">✓ 确认发布</button>
        <button class="secondary danger" :class="{ confirming: confirmDel === 'draft' }" @click="askDelete('draft')">
          {{ confirmDel === 'draft' ? '再点确认' : '🗑 删除' }}
        </button>
      </div>
    </div>

    <RestaurantEditor v-if="editing" :restaurant="shop" @saved="onSaved" @cancel="editing = false" />

    <template v-else>
      <div class="card head">
        <div class="head-top">
          <h1>{{ shop.name }}</h1>
          <div class="head-actions">
            <button class="secondary" @click="editing = true">✏️ 编辑</button>
            <button class="secondary danger" :class="{ confirming: confirmDel === 'shop' }" @click="askDelete('shop')">
              {{ confirmDel === 'shop' ? '再点确认' : '🗑 删除' }}
            </button>
          </div>
        </div>
        <div class="meta">
          <span v-if="shop.cuisine" class="tag">{{ shop.cuisine }}</span>
          <span v-if="shop.price_per_person" class="badge price">¥{{ shop.price_per_person }}/人</span>
          <span v-if="shop.my_rating != null" class="badge">我的评分 {{ shop.my_rating.toFixed(1) }} ★</span>
          <span v-if="shop.visit_count" class="badge eaten">🍽 吃过 {{ shop.visit_count }} 次</span>
          <span v-if="shop.last_visited_at" class="badge">最近 {{ fmtDate(shop.last_visited_at) }}</span>
          <span v-if="distance !== null" class="badge">📍 距你 {{ distance }} km</span>
          <a v-if="shop.source_url" :href="shop.source_url" target="_blank" rel="noopener">来源链接 ↗</a>
        </div>
        <p v-if="shop.address" class="addr">📍 {{ shop.address }}
          <a v-if="shop.lat && shop.lng" :href="`https://uri.amap.com/marker?position=${shop.lng},${shop.lat}&name=${encodeURIComponent(shop.name)}`" target="_blank" rel="noopener" class="muted">地图 ↗</a>
        </p>
        <div v-if="shop.tags && shop.tags.length" class="tags">
          <span v-for="t in shop.tags" :key="t" class="tag">{{ t }}</span>
        </div>
      </div>

      <!-- 推荐菜 -->
      <div v-if="shop.recommended_dishes && shop.recommended_dishes.length" class="card dishes">
        <div class="dishes-head">
          <h2>⭐ 推荐菜</h2>
          <button v-if="shop.source_shop_id" class="ghost" :disabled="syncing" @click="syncDishes">
            {{ syncing ? '同步中…' : '🔄 从点评同步' }}
          </button>
        </div>
        <div class="dish-grid">
          <div v-for="(dish, di) in shop.recommended_dishes" :key="di" class="dish-item">
            <img
              v-if="dish.image" :src="mediaUrl(dish.image)" alt=""
              class="dish-img" loading="lazy" decoding="async" @click="openLightbox(dishImages, di)"
            />
            <span v-else class="dish-img fallback">🍽</span>
            <div class="dish-name">{{ dish.name }}</div>
          </div>
        </div>
      </div>

      <!-- 记录一次 -->
      <div class="card visit-form">
        <h2>🍽 记录一次</h2>
        <div class="vrow">
          <label>日期 <input v-model="visit.visited_at" type="date" class="v-date" /></label>
          <button class="primary" :disabled="saving" @click="recordVisit">{{ saving ? '保存中…' : '✓ 记录' }}</button>
        </div>
        <div class="photo-picker">
          <label class="photo-add">
            ＋ 添加照片
            <input type="file" accept="image/*" multiple hidden @change="pickPhotos(visit, $event)" />
          </label>
          <div v-for="(p, i) in visit.photos" :key="p.path" class="photo-thumb">
            <img :src="p.url" alt="" />
            <button class="ghost" @click="visit.photos.splice(i, 1)">✕</button>
          </div>
        </div>
        <input v-model="visit.note" class="v-note" placeholder="备注（可选）：今天点了烤鱼，辣度刚好…" @keyup.enter="recordVisit" />
        <div v-if="visitError" class="error">{{ visitError }}</div>
      </div>

      <!-- 时间线 -->
      <div class="card timeline">
        <h2>📅 就餐记录（{{ shop.visit_count }} 次）</h2>
        <div v-if="!visits.length" class="muted">还没有记录，吃完记得回来点一下～</div>
        <div v-for="v in visits" :key="v.id" class="visit-item">
          <div v-if="editingVisit === v.id" class="v-edit">
            <div class="vrow">
              <label>日期 <input v-model="editForm.visited_at" type="date" class="v-date" /></label>
              <button class="primary" :disabled="saving" @click="saveVisitEdit(v)">💾 保存</button>
              <button class="secondary" @click="editingVisit = null">取消</button>
            </div>
            <div class="photo-picker">
              <label class="photo-add">
                ＋ 添加照片
                <input type="file" accept="image/*" multiple hidden @change="pickPhotos(editForm, $event)" />
              </label>
              <div v-for="(p, i) in editForm.photos" :key="p.path" class="photo-thumb">
                <img :src="p.url" alt="" />
                <button class="ghost" @click="editForm.photos.splice(i, 1)">✕</button>
              </div>
            </div>
            <input v-model="editForm.note" class="v-note" placeholder="备注（可选）" />
            <div v-if="visitError" class="error">{{ visitError }}</div>
          </div>
          <template v-else>
            <div class="v-head">
              <b>{{ fmtDate(v.visited_at) }}</b>
              <button class="ghost" title="编辑这条记录" @click="startEditVisit(v)">✏️</button>
              <button class="ghost" :class="{ confirming: confirmDel === v.id }" @click="askDeleteVisit(v)">
                {{ confirmDel === v.id ? '再点确认' : '✕' }}
              </button>
            </div>
            <p v-if="v.note" class="v-note-text">{{ v.note }}</p>
            <div v-if="v.photos && v.photos.length" class="v-photos">
              <img
                v-for="(ph, pi) in v.photos" :key="ph"
                :src="mediaUrl(ph)" alt=""
                class="photo-click" loading="lazy" decoding="async"
                @click="openLightbox(photosOf(v), pi)"
              />
            </div>
          </template>
        </div>
      </div>
    </template>
    <!-- 图片预览 -->
    <div v-if="lightbox" class="lightbox" @click.self="lightbox = null">
      <button class="lb-close" @click="lightbox = null">✕</button>
      <button v-if="lightboxPhotos.length > 1" class="lb-nav lb-prev" @click="lbPrev">‹</button>
      <img :src="mediaUrl(lightbox)" class="lb-img" alt="" @click.stop />
      <button v-if="lightboxPhotos.length > 1" class="lb-nav lb-next" @click="lbNext">›</button>
      <div class="lb-count muted">{{ lbIndex + 1 }} / {{ lightboxPhotos.length }}</div>
    </div>
  </template>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, mediaUrl } from '../api'
import RestaurantEditor from '../components/RestaurantEditor.vue'

const route = useRoute()
const router = useRouter()
const shop = ref(null)
const visits = ref([])
const error = ref('')
const editing = ref(false)
const saving = ref(false)
const visitError = ref('')
const confirmDel = ref(null)
const editingVisit = ref(null)
const editForm = ref({ visited_at: '', note: '', photos: [] })
let confirmTimer = null
const visit = ref({ visited_at: today(), note: '', photos: [] })

function haversine(a, b) {
  const R = 6371
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const s = Math.sin(dLat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s))
}

const distance = computed(() => {
  let pos = null
  try { pos = JSON.parse(localStorage.getItem('foodie_pos') || 'null') } catch { /* ignore */ }
  if (!pos || !shop.value || shop.value.lat == null || shop.value.lng == null) return null
  return haversine(pos, { lat: shop.value.lat, lng: shop.value.lng }).toFixed(1)
})

const stats = computed(() => {
  if (!visits.value.length) return null
  const rated = visits.value.filter((v) => v.rating)
  const costed = visits.value.filter((v) => v.cost_per_person)
  return {
    count: visits.value.length,
    avgRating: rated.length ? (rated.reduce((s, v) => s + v.rating, 0) / rated.length).toFixed(1) : null,
    avgCost: costed.length ? Math.round(costed.reduce((s, v) => s + v.cost_per_person, 0) / costed.length) : null,
  }
})

function today() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function fmtDate(s) {
  return s ? String(s).slice(0, 10) : ''
}

function askDelete(key) {
  if (confirmDel.value === key) {
    confirmDel.value = null
    clearTimeout(confirmTimer)
    remove()
    return
  }
  confirmDel.value = key
  clearTimeout(confirmTimer)
  confirmTimer = setTimeout(() => { confirmDel.value = null }, 3000)
}

function askDeleteVisit(v) {
  if (confirmDel.value === v.id) {
    confirmDel.value = null
    clearTimeout(confirmTimer)
    removeVisit(v)
    return
  }
  confirmDel.value = v.id
  clearTimeout(confirmTimer)
  confirmTimer = setTimeout(() => { confirmDel.value = null }, 3000)
}

async function pickPhotos(target, e) {
  const files = [...(e.target.files || [])]
  e.target.value = ''
  for (const f of files) {
    try {
      const res = await api.uploadImage(f)
      target.photos.push({ path: res.path, url: URL.createObjectURL(f) })
    } catch (err) { visitError.value = err.message }
  }
}

async function load() {
  try {
    shop.value = await api.getRestaurant(route.params.id)
    visits.value = await api.listVisits(route.params.id)
  } catch (e) { error.value = e.message }
}

async function publish() {
  try { shop.value = await api.publishRestaurant(route.params.id) } catch (e) { error.value = e.message }
}

const syncing = ref(false)
async function syncDishes() {
  syncing.value = true
  error.value = ''
  try {
    shop.value = await api.syncDishes(shop.value.id)
  } catch (e) { error.value = e.message } finally { syncing.value = false }
}

async function remove() {
  try { await api.deleteRestaurant(shop.value.id); router.push('/restaurants') } catch (e) { error.value = e.message }
}

async function recordVisit() {
  saving.value = true
  visitError.value = ''
  try {
    await api.addVisit(shop.value.id, {
      visited_at: visit.value.visited_at || null,
      note: visit.value.note || null,
      photos: visit.value.photos.map((p) => p.path),
    })
    visit.value = { visited_at: today(), note: '', photos: [] }
    await load()
  } catch (e) { visitError.value = e.message } finally { saving.value = false }
}

async function removeVisit(v) {
  try { await api.deleteVisit(v.id); await load() } catch (e) { error.value = e.message }
}

function startEditVisit(v) {
  editingVisit.value = v.id
  editForm.value = {
    visited_at: fmtDate(v.visited_at),
    note: v.note || '',
    photos: (v.photos || []).map((p) => ({ path: p, url: mediaUrl(p) })),
  }
  visitError.value = ''
}

async function saveVisitEdit(v) {
  saving.value = true
  visitError.value = ''
  try {
    await api.updateVisit(v.id, {
      visited_at: editForm.value.visited_at || null,
      note: editForm.value.note || null,
      photos: editForm.value.photos.map((p) => p.path),
    })
    editingVisit.value = null
    await load()
  } catch (e) { visitError.value = e.message } finally { saving.value = false }
}

async function onSaved() { editing.value = false; await load() }

// ---- 图片预览 ----
const lightbox = ref(null)
const lightboxPhotos = ref([])
const lbIndex = ref(0)

const dishImages = computed(() =>
  (shop.value?.recommended_dishes || []).map((d) => d.image).filter(Boolean)
)

function photosOf(v) {
  return (v.photos || []).map((p) => p)  // 保留路径列表
}

function openLightbox(photos, index) {
  lightboxPhotos.value = photos
  lbIndex.value = index
  lightbox.value = photos[index]
}

function lbPrev() {
  lbIndex.value = (lbIndex.value - 1 + lightboxPhotos.value.length) % lightboxPhotos.value.length
  lightbox.value = lightboxPhotos.value[lbIndex.value]
}

function lbNext() {
  lbIndex.value = (lbIndex.value + 1) % lightboxPhotos.value.length
  lightbox.value = lightboxPhotos.value[lbIndex.value]
}

onMounted(load)
</script>

<style scoped>
.back { margin-bottom: 12px; }
.draft-banner { background: #fff7e6; border: 1px solid #f5c26b; color: #8a6100; border-radius: 10px; padding: 12px 16px; margin-bottom: 14px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.banner-actions { display: flex; gap: 8px; }
.head { margin-bottom: 14px; }
.head-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.head h1 { font-size: 26px; font-weight: 800; margin-bottom: 10px; color: #2f2a24; }
.head-actions { display: flex; gap: 8px; }
.meta { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
.meta a { color: #e5533c; font-size: 13px; }
.price { color: #d94a33; font-weight: 600; }
.eaten { background: #e8f5e9; color: #2e7d32; }
.addr { font-size: 14px; color: #555; }
.tags { margin-top: 8px; }
.visit-form { margin-bottom: 14px; }
.visit-form h2 { font-size: 17px; margin-bottom: 10px; color: #e5533c; }
.vrow { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 8px; }
.vrow label { font-size: 13px; color: #888; display: flex; flex-direction: column; gap: 4px; }
.v-date { width: auto; }
.photo-picker { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.photo-add {
  display: inline-block; background: #f0ece6; color: #555; border-radius: 8px;
  padding: 6px 12px; font-size: 13px; cursor: pointer;
}
.photo-thumb { position: relative; }
.photo-thumb img { width: 64px; height: 64px; object-fit: cover; border-radius: 8px; }
.photo-thumb button { position: absolute; top: -6px; right: -6px; background: #d33; color: #fff; border-radius: 50%; width: 20px; height: 20px; font-size: 11px; padding: 0; }
.v-note { margin-bottom: 6px; }
.dishes { margin-bottom: 14px; }
.dishes-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.dishes h2 { font-size: 17px; font-weight: 700; color: var(--brand-deep); margin: 0; }
.dish-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; }
.dish-item { text-align: center; }
.dish-img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 10px; cursor: zoom-in; }
.dish-img.fallback { background: #f5efe8; display: flex; align-items: center; justify-content: center; font-size: 32px; }
.dish-name { margin-top: 6px; font-size: 13px; color: #444; }
.timeline h2 { font-size: 17px; font-weight: 700; margin-bottom: 10px; color: var(--brand-deep); }
.visit-item { padding: 10px 0; border-bottom: 1px dashed #eee; }
.v-head { display: flex; align-items: center; gap: 8px; }
.v-note-text { color: #555; font-size: 14px; margin-top: 4px; }
.v-photos { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.v-photos img { width: 80px; height: 80px; object-fit: cover; border-radius: 8px; cursor: zoom-in; }
.lightbox {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.88); z-index: 100;
  display: flex; align-items: center; justify-content: center;
}
.lb-img { max-width: 92vw; max-height: 88vh; border-radius: 6px; }
.lb-close {
  position: absolute; top: 16px; right: 16px; background: rgba(255, 255, 255, 0.15);
  color: #fff; width: 40px; height: 40px; border-radius: 50%; font-size: 18px;
}
.lb-nav {
  position: absolute; top: 50%; transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.15); color: #fff;
  width: 44px; height: 60px; border-radius: 8px; font-size: 26px;
}
.lb-prev { left: 16px; }
.lb-next { right: 16px; }
.lb-count { position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); color: #ddd; }
.confirming { background: #d33 !important; color: #fff !important; }
.danger { background: #fdecec; color: #d33; }

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .head h1 { font-size: 20px; }
  .dish-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .dish-name { font-size: 12px; }
  .v-photos img { width: 96px; height: 96px; }
  .photo-thumb img { width: 72px; height: 72px; }
  .lb-nav { width: 38px; height: 52px; }
  .lb-prev { left: 8px; }
  .lb-next { right: 8px; }
  .vrow { gap: 8px; }
}
</style>
