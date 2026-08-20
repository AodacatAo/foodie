<template>
  <div>
    <div class="head">
      <div>
        <h1>📋 菜单 · 点餐</h1>
        <p class="muted">
          {{ menuItems.length }} 道菜在菜单上
          <span v-if="wantCount"> · 今天想吃 {{ wantCount }} 道</span>
          <span v-if="totalPrice !== null" class="total"> · 合计 ¥{{ totalPrice }}</span>
        </p>
      </div>
      <button class="qr-btn" @click="openQr">📱 扫码点餐</button>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-else-if="loading && !menuItems.length" class="empty">加载中…</div>
    <div v-else-if="!menuItems.length" class="empty menu-empty">
      菜单还是空的
      <p class="muted">去「菜谱库」点卡片右上角的「🍽 上架」，把想吃的菜加进来</p>
    </div>

    <div class="grid" v-else>
      <div
        v-for="r in sorted" :key="r.id"
        class="card menu-card"
        :class="{ wanted: r.menu_want }"
      >
        <div class="cover">
          <img v-if="r.cover_image" :src="mediaUrl(r.cover_image)" alt="" loading="lazy" decoding="async" @click="$router.push(`/recipe/${r.id}`)" />
          <span v-else class="cover-fallback" @click="$router.push(`/recipe/${r.id}`)">🍳</span>
          <button
            class="want-btn"
            :class="{ on: r.menu_want }"
            @click.stop.prevent="toggleWant(r)"
          >{{ r.menu_want ? '❤️ 想吃' : '🤍 想吃' }}</button>
          <button
            class="off-btn"
            title="从菜单下架"
            @click.stop.prevent="takeOff(r)"
          >✕</button>
        </div>
        <div class="body">
          <div class="title-row">
            <h3 @click="$router.push(`/recipe/${r.id}`)">{{ r.title }}</h3>
            <span
              v-if="editingPrice !== r.id"
              class="price"
              :class="{ unset: r.menu_price == null }"
              title="点击设置价格"
              @click.stop.prevent="startEditPrice(r)"
            >{{ r.menu_price != null ? `¥${r.menu_price}` : '定价' }}</span>
            <input
              v-else
              v-model.number="priceDraft"
              type="number" min="0" max="99999" step="0.1"
              class="price-input"
              placeholder="元"
              @keyup.enter="savePrice(r)"
              @blur="savePrice(r)"
              @click.stop
              ref="priceInput"
            />
          </div>
          <div class="meta">
            <span v-if="r.cooking_time_min" class="badge">⏱ {{ r.cooking_time_min }} 分钟</span>
            <span v-if="r.servings" class="badge">{{ r.servings }}</span>
          </div>
          <div class="cat-row">
            <span
              class="cat-chip"
              :class="{ set: r.menu_category, editing: editingCat === r.id }"
              @click.stop.prevent="toggleCatEdit(r)"
            >{{ r.menu_category ? `🏷 ${r.menu_category}` : '＋ 分类' }}</span>
            <div v-if="editingCat === r.id" class="cat-picker" @click.stop>
              <button
                v-for="c in presetCats" :key="c"
                class="chip-mini"
                :class="{ on: r.menu_category === c }"
                @click="setCat(r, c)"
              >{{ c }}</button>
              <input v-model="catDraft" class="cat-input" placeholder="自定义…" @keyup.enter="setCat(r, catDraft)" />
              <button class="chip-mini none" @click="setCat(r, '')">清除</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 点单记录 -->
    <div v-if="orders.length" class="card orders-card">
      <h2>📜 点单记录</h2>
      <div v-for="o in orders" :key="o.id" class="order-item">
        <div class="order-line">
          <b>{{ o.person || '家人' }}</b>
          <span class="muted">{{ fmtTime(o.created_at) }}</span>
          <span class="order-total">¥{{ o.total }}</span>
          <button class="ghost" title="删除记录" @click="removeOrder(o)">✕</button>
        </div>
        <div class="order-items muted">
          <span v-for="(it, i) in o.items" :key="i">{{ it.title }}×{{ it.qty }}<span v-if="i < o.items.length - 1">、</span></span>
        </div>
      </div>
    </div>

    <!-- 扫码点餐弹窗 -->
    <div v-if="showQr" class="qr-overlay" @click.self="showQr = false">
      <div class="qr-card">
        <h2>📱 扫码点餐</h2>
        <p class="muted">手机连同一个 Wi-Fi，用微信扫一扫打开菜单</p>
        <img v-if="qrDataUrl" :src="qrDataUrl" class="qr-img" alt="扫码点餐二维码" />
        <code class="qr-url">{{ menuUrl }}</code>
        <button class="secondary" @click="showQr = false">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import QRCode from 'qrcode'
import { api, mediaUrl } from '../api'

const items = ref([])
const error = ref('')
const loading = ref(false)
const showQr = ref(false)
const qrDataUrl = ref('')
const menuUrl = computed(() => `${window.location.origin}/#/order`)
const editingPrice = ref(null)
const editingCat = ref(null)
const catDraft = ref('')
const presetCats = ['热菜', '凉菜', '汤', '主食', '小吃', '饮品', '甜品']

function toggleCatEdit(r) {
  editingCat.value = editingCat.value === r.id ? null : r.id
  catDraft.value = ''
}

async function setCat(r, cat) {
  const val = (cat || '').trim().slice(0, 20)
  editingCat.value = null
  if (val === (r.menu_category || '')) return
  try {
    const updated = await api.setMenuCategory(r.id, val || null)
    r.menu_category = updated.menu_category
  } catch (e) {
    error.value = e.message
  }
}
const priceDraft = ref(null)
const priceInput = ref(null)

const menuItems = computed(() => items.value.filter((r) => r.on_menu))
const wantCount = computed(() => menuItems.value.filter((r) => r.menu_want).length)
// 合计：勾选「想吃」的菜价求和
const totalPrice = computed(() => {
  const wanted = menuItems.value.filter((r) => r.menu_want)
  if (!wanted.length) return null
  const sum = wanted.reduce((s, r) => s + (r.menu_price ?? 0), 0)
  return sum
})
// 想吃置顶 → 最近上架在前
const sorted = computed(() =>
  [...menuItems.value].sort((a, b) => {
    if (a.menu_want !== b.menu_want) return a.menu_want ? -1 : 1
    return new Date(b.menu_at || 0) - new Date(a.menu_at || 0)
  })
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.listRecipes({ page_size: 200, status: 'published' })
    items.value = data.items
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function toggleWant(r) {
  try {
    const updated = await api.toggleWant(r.id)
    r.menu_want = updated.menu_want
  } catch (e) {
    error.value = e.message
  }
}

async function takeOff(r) {
  try {
    await api.takeOffMenu(r.id)
    r.on_menu = false
    r.menu_want = false
  } catch (e) {
    error.value = e.message
  }
}

async function startEditPrice(r) {
  editingPrice.value = r.id
  priceDraft.value = r.menu_price
  await nextTick()
  if (priceInput.value) priceInput.value.focus()
}

async function savePrice(r) {
  if (editingPrice.value !== r.id) return
  const val = priceDraft.value
  editingPrice.value = null
  const price = val == null || val === '' ? null : Math.round(val * 10) / 10
  if (price === r.menu_price) return
  try {
    const updated = await api.setMenuPrice(r.id, price)
    r.menu_price = updated.menu_price
  } catch (e) {
    error.value = e.message
  }
}

const orders = ref([])

async function loadOrders() {
  try {
    const data = await api.listOrders({ page_size: 20 })
    orders.value = data.items
  } catch { /* 忽略 */ }
}

function fmtTime(s) {
  if (!s) return ''
  const d = new Date(s)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function removeOrder(o) {
  try {
    await api.deleteOrder(o.id)
    orders.value = orders.value.filter((x) => x.id !== o.id)
  } catch (e) {
    error.value = e.message
  }
}

async function openQr() {
  showQr.value = true
  if (!qrDataUrl.value) {
    try {
      qrDataUrl.value = await QRCode.toDataURL(menuUrl.value, { width: 260, margin: 1 })
    } catch (e) {
      error.value = '二维码生成失败：' + e.message
    }
  }
}

onMounted(() => { load(); loadOrders() })
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 14px; flex-wrap: wrap; gap: 8px; }
.head h1 { font-size: 22px; }
.total { color: var(--brand-deep); font-weight: 700; }
.qr-btn { background: #2e7d32; }
.qr-btn:hover { opacity: 0.9; }
.menu-empty { line-height: 2; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.menu-card { padding: 0; overflow: hidden; transition: transform 0.12s, box-shadow 0.12s; }
.menu-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); }
.menu-card.wanted { border: 2px solid var(--brand); }
.cover { position: relative; height: 150px; background: #f5efe8; display: flex; align-items: center; justify-content: center; }
.cover img { width: 100%; height: 100%; object-fit: cover; cursor: pointer; transition: transform 0.35s ease; }
.menu-card:hover .cover img { transform: scale(1.06); }
.cover-fallback { font-size: 40px; cursor: pointer; }
.want-btn {
  position: absolute; bottom: 8px; left: 8px;
  background: rgba(0, 0, 0, 0.55); color: #fff;
  border-radius: 16px; padding: 4px 12px;
  font-size: 13px; font-weight: 600;
  backdrop-filter: blur(4px);
}
.want-btn.on { background: var(--brand); }
.off-btn {
  position: absolute; top: 8px; right: 8px;
  background: rgba(0, 0, 0, 0.5); color: #fff;
  border-radius: 50%; width: 28px; height: 28px;
  padding: 0; font-size: 14px;
  display: none; align-items: center; justify-content: center;
}
.menu-card:hover .off-btn { display: inline-flex; }
.off-btn:hover { background: #d33; }
.body { padding: 12px 14px; }
.title-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 7px; }
.title-row h3 { font-size: 15.5px; font-weight: 700; color: #2f2a24; cursor: pointer; flex: 1; min-width: 0; }
.price {
  flex: none; font-size: 15px; font-weight: 800; color: var(--brand-deep);
  cursor: pointer; padding: 2px 8px; border-radius: 8px; background: var(--brand-soft);
}
.price.unset { color: #a08d7a; font-weight: 600; font-size: 13px; }
.price-input { flex: none; width: 74px; padding: 3px 8px; font-size: 14px; border-radius: 8px; }
.meta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }

/* 分类 */
.cat-row { position: relative; margin-top: 6px; }
.cat-chip {
  display: inline-block; font-size: 12px; color: #a08d7a; cursor: pointer;
  background: #f7f3ec; border-radius: 10px; padding: 2px 9px;
}
.cat-chip.set { color: #7a5b2e; background: #fdf3dc; font-weight: 600; }
.cat-picker {
  position: absolute; left: 0; top: 26px; z-index: 30;
  background: #fff; border-radius: 10px; padding: 8px;
  box-shadow: var(--shadow-lg); border: 1px solid var(--line);
  display: flex; flex-wrap: wrap; gap: 6px; width: 220px;
}
.chip-mini {
  background: #f3ede5; color: #6b5d4e; border-radius: 14px;
  padding: 3px 10px; font-size: 12px; font-weight: 500;
}
.chip-mini.on { background: var(--brand); color: #fff; }
.chip-mini.none { background: #fdecec; color: #d33; }
.cat-input { width: 90px; padding: 2px 8px; font-size: 12px; border-radius: 14px; }

/* 点单记录 */
.orders-card { margin-top: 18px; }
.orders-card h2 { font-size: 16px; font-weight: 700; color: #2f2a24; margin-bottom: 10px; }
.order-item { padding: 9px 0; border-bottom: 1px dashed var(--line); }
.order-item:last-child { border-bottom: none; }
.order-line { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.order-total { margin-left: auto; color: var(--brand-deep); font-weight: 800; font-size: 15px; }
.order-items { font-size: 12.5px; margin-top: 2px; }

/* 扫码弹窗 */
.qr-overlay {
  position: fixed; inset: 0; z-index: 120;
  background: rgba(0, 0, 0, 0.55);
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.qr-card {
  background: #fff; border-radius: 16px; padding: 24px;
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  max-width: 340px; width: 100%; text-align: center;
}
.qr-card h2 { font-size: 18px; color: #2f2a24; }
.qr-img { width: 240px; height: 240px; border-radius: 8px; }
.qr-url { font-size: 12px; color: #888; word-break: break-all; background: #f7f3ec; padding: 4px 10px; border-radius: 6px; }

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .cover { height: 96px; }
  .cover-fallback { font-size: 32px; }
  .off-btn { display: inline-flex; width: 26px; height: 26px; }
  .body { padding: 8px 10px; }
  .title-row h3 { font-size: 14px; }
  .price { font-size: 13.5px; }
  .qr-btn { width: 100%; }
}
</style>
