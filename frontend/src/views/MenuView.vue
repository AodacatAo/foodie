<template>
  <div class="menu-page">
    <!-- Hero 渐变头 -->
    <header class="hero">
      <div class="blob blob-a"></div>
      <div class="blob blob-b"></div>
      <div class="hero-inner">
        <div class="hero-mark"><Icon name="menu" :size="24" /></div>
        <div class="hero-text">
          <h1 class="hero-title">菜单 · 点餐</h1>
          <p class="hero-sub">
            {{ menuItems.length }} 道菜在菜单上
            <span v-if="wantCount"> · 想吃 {{ wantCount }} 道</span>
            <span v-if="totalPrice !== null" class="hero-total"> · 合计 ¥{{ totalPrice }}</span>
          </p>
        </div>
        <div class="hero-actions">
          <a class="hero-btn" :href="menuPdfUrl" target="_blank" rel="noopener"><Icon name="printer" :size="15" /> 打印</a>
          <button class="hero-btn primary" @click="openQr"><Icon name="qr" :size="15" /> 扫码点餐</button>
        </div>
      </div>
    </header>

    <div class="content">
      <div v-if="error" class="error">{{ error }}</div>
      <div v-else-if="loading && !menuItems.length" class="empty">加载中…</div>
      <div v-else-if="!menuItems.length" class="empty menu-empty">
        菜单还是空的
        <p class="muted">去「菜谱库」点卡片右上角的「🍽 上架」，把想吃的菜加进来</p>
      </div>

      <div v-else class="grid">
        <div
          v-for="(r, i) in sorted" :key="r.id"
          class="card menu-card"
          :class="{ wanted: r.menu_want }"
          :style="{ '--i': i }"
        >
          <div class="cover">
            <img v-if="r.cover_image" :src="mediaUrl(r.cover_image)" alt="" loading="lazy" decoding="async" @click="$router.push(`/recipe/${r.id}`)" />
            <span v-else class="cover-fallback" @click="$router.push(`/recipe/${r.id}`)">🍳</span>
            <button
              class="want-btn"
              :class="{ on: r.menu_want }"
              @click.stop.prevent="toggleWant(r)"
            ><Icon name="heart" :size="13" :stroke="r.menu_want ? 2.2 : 1.8" /> 想吃</button>
            <button
              class="off-btn"
              title="从菜单下架"
              @click.stop.prevent="takeOff(r)"
            ><Icon name="close" :size="14" /></button>
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
              >{{ r.menu_price != null ? '¥' + r.menu_price : '定价' }}</span>
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
              <span v-if="r.cooking_time_min" class="meta-ic"><Icon name="clock" :size="12" /> {{ r.cooking_time_min }} 分钟</span>
              <span v-if="r.servings" class="meta-ic"><Icon name="servings" :size="12" /> {{ r.servings }}</span>
            </div>
            <div class="cat-row">
              <span
                class="cat-chip"
                :class="{ set: r.menu_category, editing: editingCat === r.id }"
                @click.stop.prevent="toggleCatEdit(r)"
              >{{ r.menu_category ? r.menu_category : '＋ 分类' }}</span>
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

      <!-- 点单记录：进度可视化 -->
      <div v-if="orders.length" class="card orders-card">
        <h2><Icon name="menu" :size="16" /> 点单记录</h2>
        <div v-for="(o, i) in orders" :key="o.id" class="order-item" :style="{ '--i': i }">
          <div class="order-line">
            <span class="order-person"><Icon name="bowl" :size="13" />{{ o.person || '家人' }}</span>
            <span class="status-chip" :class="o.status">{{ statusLabel(o.status) }}</span>
            <span class="muted">{{ fmtTime(o.created_at) }}</span>
            <span class="order-total">¥{{ o.total }}</span>
            <button class="ghost del-btn" title="删除记录" @click="removeOrder(o)"><Icon name="trash" :size="14" /></button>
          </div>
          <div class="order-items muted">
            <span v-for="(it, j) in o.items" :key="j">{{ it.title }}×{{ it.qty }}<span v-if="j < o.items.length - 1">、</span></span>
          </div>
          <div class="order-actions">
            <div class="mini-track">
              <span v-for="(s, si) in ['pending', 'making', 'served']" :key="s" class="mini-dot"
                :class="{ on: ['pending', 'making', 'served'].indexOf(s) <= ['pending', 'making', 'served'].indexOf(o.status), pulse: s === o.status && o.status !== 'served' }"></span>
            </div>
            <template v-if="o.status !== 'served'">
              <button v-if="o.status === 'pending'" class="chip-mini advance" @click="advanceOrder(o, 'making')">👨‍🍳 开始制作</button>
              <button v-else-if="o.status === 'making'" class="chip-mini advance serving" @click="advanceOrder(o, 'served')"><Icon name="check" :size="12" /> 上菜</button>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- 扫码点餐弹窗 -->
    <div v-if="showQr" class="qr-overlay" @click.self="showQr = false">
      <div class="qr-card">
        <h2><Icon name="qr" :size="18" /> 扫码点餐</h2>
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
import Icon from '../components/Icon.vue'

const items = ref([])
const error = ref('')
const loading = ref(false)
const showQr = ref(false)
const qrDataUrl = ref('')
const menuUrl = computed(() => `${window.location.origin}/#/order`)
const menuPdfUrl = computed(() => api.menuPdfUrl(window.location.origin))
const editingPrice = ref(null)
const editingCat = ref(null)
const catDraft = ref('')
const presetCats = ['热菜', '凉菜', '汤', '主食', '小吃', '饮品', '甜品']

const STATUS_LABEL = { pending: '已下单', making: '制作中', served: '已上菜' }
function statusLabel(s) { return STATUS_LABEL[s] || s }

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

async function advanceOrder(o, status) {
  try {
    const updated = await api.setOrderStatus(o.id, status)
    o.status = updated.status
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
.menu-page {
  background:
    radial-gradient(900px 500px at 85% -80px, rgba(240, 106, 79, 0.14), transparent 60%),
    radial-gradient(700px 400px at -15% 30%, rgba(245, 166, 35, 0.10), transparent 60%),
    var(--bg);
  min-height: 100vh;
  margin: -26px -20px -64px;
  padding: 26px 20px 70px;
}
/* ---- Hero ---- */
.hero {
  position: relative; overflow: hidden;
  background: linear-gradient(135deg, #f4704f 0%, #e5533c 52%, #d43a2a 100%);
  border-radius: 24px;
  padding: 22px 22px;
  color: #fff;
  box-shadow: 0 14px 34px rgba(229, 83, 60, 0.28);
  margin-bottom: 16px;
}
.blob { position: absolute; border-radius: 50%; filter: blur(46px); opacity: 0.55; pointer-events: none; animation: blob-float 9s ease-in-out infinite alternate; }
.blob-a { width: 220px; height: 220px; background: rgba(255, 214, 145, 0.85); top: -60px; left: -50px; }
.blob-b { width: 180px; height: 180px; background: rgba(255, 122, 88, 0.8); bottom: -70px; right: -30px; animation-delay: -4.5s; }
@keyframes blob-float { from { transform: translate(0, 0) scale(1); } to { transform: translate(26px, 14px) scale(1.14); } }
.hero-inner { position: relative; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.hero-mark {
  width: 50px; height: 50px; border-radius: 16px; flex: none;
  background: rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.35);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}
.hero-text { flex: 1; min-width: 0; }
.hero-title { font-size: 22px; font-weight: 800; letter-spacing: 1px; text-shadow: 0 2px 8px rgba(0, 0, 0, 0.14); }
.hero-sub { font-size: 12.5px; opacity: 0.95; margin-top: 3px; }
.hero-total { font-weight: 800; color: #ffe0d6; }
.hero-actions { display: flex; gap: 8px; width: 100%; }
.hero-btn {
  flex: 1; justify-content: center;
  background: rgba(255, 255, 255, 0.16); color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.24);
  display: inline-flex; align-items: center; gap: 6px;
  padding: 9px 14px; border-radius: 12px;
  font-size: 14px; font-weight: 600; text-decoration: none;
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
  transition: background 0.15s, transform 0.15s;
}
.hero-btn:hover { background: rgba(255, 255, 255, 0.28); }
.hero-btn:active { transform: scale(0.97); }
.hero-btn.primary { background: #fff; color: #c9442e; font-weight: 800; }
.hero-btn.primary:hover { background: #fff4ef; }

/* ---- 卡片 ---- */
.menu-empty { line-height: 2; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.menu-card { padding: 0; overflow: hidden; transition: transform 0.12s, box-shadow 0.12s, border-color 0.2s; animation: rise 0.5s ease both; animation-delay: calc(var(--i) * 55ms); }
@keyframes rise { from { opacity: 0; transform: translateY(16px) scale(0.98); } to { opacity: 1; transform: none; } }
.menu-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); }
.menu-card.wanted { border: 2px solid rgba(229, 83, 60, 0.5); box-shadow: 0 8px 22px rgba(229, 83, 60, 0.10); }
.cover { position: relative; height: 150px; background: #f5efe8; display: flex; align-items: center; justify-content: center; }
.cover img { width: 100%; height: 100%; object-fit: cover; cursor: pointer; transition: transform 0.35s ease; }
.menu-card:hover .cover img { transform: scale(1.06); }
.cover-fallback { font-size: 40px; cursor: pointer; }
.want-btn {
  position: absolute; bottom: 8px; left: 8px;
  background: rgba(28, 24, 20, 0.55); color: #fff;
  border-radius: 16px; padding: 4px 12px;
  font-size: 13px; font-weight: 600;
  display: inline-flex; align-items: center; gap: 4px;
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
}
.want-btn.on { background: var(--brand-grad); box-shadow: 0 2px 8px rgba(229, 83, 60, 0.35); animation: want-pop 0.3s ease; }
@keyframes want-pop { 0% { transform: scale(0.8); } 60% { transform: scale(1.1); } 100% { transform: scale(1); } }
.want-btn.on :deep(.icon) { fill: currentColor; }
.off-btn {
  position: absolute; top: 8px; right: 8px;
  background: rgba(0, 0, 0, 0.42); color: #fff;
  border-radius: 10px; width: 30px; height: 30px;
  padding: 0; font-size: 14px;
  display: none; align-items: center; justify-content: center;
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
}
.menu-card:hover .off-btn { display: inline-flex; }
.off-btn:hover { background: #d33; opacity: 1; }
.body { padding: 12px 14px; }
.title-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 7px; }
.title-row h3 { font-size: 15.5px; font-weight: 700; color: #2f2a24; cursor: pointer; flex: 1; min-width: 0; }
.price {
  flex: none; font-size: 15px; font-weight: 800; color: var(--brand-deep);
  cursor: pointer; padding: 2px 8px; border-radius: 8px; background: var(--brand-soft);
}
.price i { font-style: normal; font-size: 12px; }
.price.unset { color: #a08d7a; font-weight: 600; font-size: 13px; }
.price-input { flex: none; width: 74px; padding: 3px 8px; font-size: 14px; border-radius: 8px; }
.meta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }
.meta-ic { display: inline-flex; align-items: center; gap: 3px; color: #a08d7a; font-size: 12px; background: #f7f3ec; border-radius: 10px; padding: 2px 8px; }

/* 分类 */
.cat-row { position: relative; margin-top: 6px; }
.cat-chip {
  display: inline-block; font-size: 12px; color: #a08d7a; cursor: pointer;
  background: #f7f3ec; border-radius: 10px; padding: 2px 9px;
}
.cat-chip.set { color: #7a5b2e; background: #fdf3dc; font-weight: 600; }
.cat-picker {
  position: absolute; left: 0; top: 26px; z-index: 30;
  background: #fff; border-radius: 12px; padding: 8px;
  box-shadow: var(--shadow-lg); border: 1px solid var(--line);
  display: flex; flex-wrap: wrap; gap: 6px; width: 220px;
}
.chip-mini {
  background: #f3ede5; color: #6b5d4e; border-radius: 14px;
  padding: 3px 10px; font-size: 12px; font-weight: 500;
  display: inline-flex; align-items: center; gap: 4px;
}
.chip-mini.on { background: var(--brand); color: #fff; }
.chip-mini.none { background: #fdecec; color: #d33; }
.cat-input { width: 90px; padding: 2px 8px; font-size: 12px; border-radius: 14px; }

/* 点单记录 */
.orders-card { margin-top: 18px; }
.orders-card h2 { display: flex; align-items: center; gap: 6px; font-size: 16px; font-weight: 800; color: #2f2a24; margin-bottom: 10px; }
.order-item { padding: 12px 0; border-bottom: 1px dashed var(--line); animation: rise 0.4s ease both; animation-delay: calc(var(--i) * 40ms); }
.order-item:last-child { border-bottom: none; }
.order-line { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.order-person { display: inline-flex; align-items: center; gap: 4px; color: #2f2a24; font-weight: 700; }
.order-total { margin-left: auto; color: var(--brand-deep); font-weight: 800; font-size: 15px; }
.del-btn { display: inline-flex; }
.order-items { font-size: 12.5px; margin-top: 3px; }
.status-chip { font-size: 11px; font-weight: 700; border-radius: 10px; padding: 1px 8px; }
.status-chip.pending { background: #fff3e0; color: #c97900; }
.status-chip.making { background: #e3f2fd; color: #1565c0; }
.status-chip.served { background: #e8f5e9; color: #2e7d32; }
.order-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
.mini-track { display: flex; align-items: center; gap: 5px; }
.mini-dot { width: 9px; height: 9px; border-radius: 50%; background: #e8dfd2; transition: background 0.3s; }
.mini-dot.on { background: var(--brand); }
.mini-dot.pulse { animation: dot-pulse2 1.2s ease-in-out infinite; }
@keyframes dot-pulse2 { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.4); } }
.chip-mini.advance { cursor: pointer; }
.chip-mini.advance.serving { background: #2e7d32; color: #fff; }

/* 扫码弹窗 */
.qr-overlay {
  position: fixed; inset: 0; z-index: 120;
  background: rgba(30, 22, 14, 0.55);
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.qr-card {
  background: rgba(255, 255, 255, 0.96); border-radius: 20px; padding: 24px;
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  max-width: 340px; width: 100%; text-align: center;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.28);
  animation: rise 0.25s ease;
}
.qr-card h2 { display: flex; align-items: center; gap: 6px; font-size: 18px; color: #2f2a24; }
.qr-img { width: 240px; height: 240px; border-radius: 12px; background: #fff; padding: 6px; }
.qr-url { font-size: 12px; color: #888; word-break: break-all; background: #f7f3ec; padding: 4px 10px; border-radius: 6px; }

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .menu-page { margin: -14px -12px -96px; padding: 14px 12px 100px; }
  .hero { padding: 18px 16px; border-radius: 20px; }
  .hero-title { font-size: 20px; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .cover { height: 96px; }
  .cover-fallback { font-size: 32px; }
  .off-btn { display: inline-flex; width: 26px; height: 26px; }
  .body { padding: 8px 10px; }
  .title-row h3 { font-size: 14px; }
  .price { font-size: 13.5px; }
}
</style>
