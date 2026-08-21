<template>
  <div class="order-page">
    <!-- 顶部 Hero：品牌渐变 + 漂浮光斑 -->
    <header class="hero">
      <div class="blob blob-a"></div>
      <div class="blob blob-b"></div>
      <div class="hero-inner">
        <div class="hero-mark"><Icon name="bowl" :size="26" /></div>
        <div class="hero-title">
          <h1>食集菜单</h1>
          <p>{{ todayText }} · {{ menuItems.length }} 道菜 · 今天想吃点啥</p>
        </div>
        <div v-if="orderedCount" class="hero-badge">{{ orderedCount }} 道已选</div>
      </div>
    </header>

    <!-- 分类栏：毛玻璃胶囊 -->
    <nav v-if="categories.length" class="cat-bar">
      <button
        v-for="c in ['全部', ...categories]" :key="c"
        class="cat-tab"
        :class="{ on: activeCat === c }"
        @click="activeCat = c"
      >{{ c }}</button>
    </nav>

    <div class="content">
      <div v-if="error" class="error">{{ error }}</div>
      <div v-else-if="loading && !menuItems.length" class="empty">加载中…</div>
      <div v-else-if="!menuItems.length" class="empty menu-empty">
        菜单还没准备好
        <p class="muted">请稍后再来～</p>
      </div>

      <div v-else-if="!filtered.length" class="empty menu-empty">这个分类还没有菜</div>

      <!-- 菜品列表：交错入场动画 -->
      <div v-else :key="activeCat" class="dish-list">
        <div
          v-for="(r, i) in filtered" :key="r.id"
          class="dish-row"
          :class="{ ordered: cartQty(r.id) > 0 }"
          :style="{ '--i': i }"
        >
          <div class="dish-img-wrap">
            <img v-if="r.cover_image" :src="mediaUrl(r.cover_image)" class="dish-img" alt="" loading="lazy" decoding="async" />
            <span v-else class="dish-img fallback">🍳</span>
            <span v-if="r.menu_category" class="dish-cat">{{ r.menu_category }}</span>
          </div>
          <div class="dish-info">
            <h3>{{ r.title }}</h3>
            <div class="dish-meta">
              <Icon v-if="r.cooking_time_min" name="clock" :size="12" />
              <span v-if="r.cooking_time_min">{{ r.cooking_time_min }} 分钟</span>
              <Icon v-if="r.servings" name="servings" :size="12" />
              <span v-if="r.servings">{{ r.servings }}</span>
            </div>
            <div class="price-row">
              <span class="price" :class="{ unset: r.menu_price == null }">
                <template v-if="r.menu_price != null"><i>¥</i>{{ r.menu_price }}</template>
                <template v-else>时价</template>
              </span>
              <!-- 美团式数量控件：份数变化时弹跳 -->
              <div class="qty-ctrl">
                <button
                  v-if="cartQty(r.id) > 0"
                  class="qty-btn minus" @click="changeQty(r, -1)"
                ><Icon name="minus" :size="15" /></button>
                <span v-if="cartQty(r.id) > 0" :key="cartQty(r.id)" class="qty-num pop">{{ cartQty(r.id) }}</span>
                <button class="qty-btn plus" @click="changeQty(r, 1)">
                  <Icon name="plus" :size="15" />
                  <span class="ripple" v-if="justAdded === r.id" :key="r.id + cartQty(r.id)"></span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部购物车悬浮条 -->
      <div class="order-bar" :class="{ open: cartOpen }" @click="cartOpen = true">
        <div class="cart-icon" :class="{ on: orderedCount }">
          <Icon name="cart" :size="21" />
          <span v-if="orderedCount" :key="orderedCount" class="cart-badge pop">{{ orderedCount }}</span>
        </div>
        <div class="order-summary">
          <template v-if="orderedCount">
            <span class="summary-title">已点 {{ orderedCount }} 道</span>
            <span class="summary-total">合计 <b>¥{{ totalPrice ?? 0 }}</b></span>
          </template>
          <span v-else class="cart-empty">还没有点菜，逛逛菜单吧</span>
        </div>
        <span class="cart-arrow"><Icon name="back" :size="16" /></span>
      </div>
    </div>

    <!-- 购物车弹层 -->
    <transition name="sheet">
      <div v-if="cartOpen" class="cart-panel">
        <div class="sheet-handle"></div>
        <div class="cart-head">
          <h3>已点菜品</h3>
          <button class="ghost clear-btn" @click="clearAll"><Icon name="trash" :size="13" /> 清空</button>
        </div>
        <div v-if="!ordered.length" class="cart-empty-list muted">还没有点菜</div>
        <div v-for="r in ordered" :key="r.id" class="cart-item">
          <img v-if="r.cover_image" :src="mediaUrl(r.cover_image)" alt="" class="cart-thumb" />
          <span v-else class="cart-thumb fallback">🍳</span>
          <div class="cart-item-info">
            <span class="cart-name">{{ r.title }}</span>
            <span class="cart-unit muted">¥{{ r.menu_price ?? '时价' }} / 份</span>
          </div>
          <div class="qty-ctrl">
            <button class="qty-btn minus" @click.stop="changeQty(r, -1)"><Icon name="minus" :size="14" /></button>
            <span :key="r.qty" class="qty-num pop">{{ r.qty }}</span>
            <button class="qty-btn plus" @click.stop="changeQty(r, 1)"><Icon name="plus" :size="14" /></button>
          </div>
        </div>
        <div v-if="totalPrice" class="cart-total">
          合计 <b>¥{{ totalPrice }}</b><span v-if="hasUnpriced" class="muted">（含时价菜）</span>
        </div>
        <div class="cart-submit">
          <input
            v-model="personName" class="person-input"
            placeholder="你的名字（可选）" @click.stop
          />
          <button class="submit-btn shine" :disabled="submitting" @click.stop="submitOrder">
            <template v-if="submitting">下单中…</template>
            <template v-else-if="orderedCount">
              <Icon name="check" :size="16" /> 下单 ¥{{ totalPrice ?? 0 }}
            </template>
            <template v-else>去点菜</template>
          </button>
        </div>

        <p v-if="orderDone" class="order-done">✅ 已下单！{{ orderDoneMsg }}</p>

        <!-- 订单进度：动效化 -->
        <div v-if="orderStatus" class="status-card">
          <div class="status-track">
            <div class="status-fill" :style="{ width: statusPct + '%' }"></div>
            <span
              v-for="(s, i) in STATUS_STEPS" :key="s"
              class="status-step"
              :class="{ on: i <= statusIndex, pulse: i === statusIndex && orderStatus.status !== 'served' }"
            >
              <span class="dot"></span>{{ s }}
            </span>
          </div>
          <p class="status-hint">
            {{ orderStatus.status === 'served' ? '菜都上齐啦，开吃！🍚' : '后厨正在准备，本页会自动刷新进度～' }}
          </p>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="cart-close" @click="cartOpen = false">收起 ▾</button>
      </div>
    </transition>

    <!-- 下单成功撒花 -->
    <canvas v-show="confettiOn" ref="confettiEl" class="confetti"></canvas>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { api, mediaUrl } from '../api'
import Icon from '../components/Icon.vue'

const CART_KEY = 'foodie_cart_v1'
const items = ref([])
const error = ref('')
const loading = ref(false)
const cartOpen = ref(false)
const justAdded = ref(null)
let addedTimer = null

// 购物车：存本机 localStorage（每台手机各自独立，互不干扰）
function loadCart() {
  try {
    const raw = JSON.parse(localStorage.getItem(CART_KEY) || '{}')
    const out = {}
    for (const [k, v] of Object.entries(raw)) {
      const qty = Number(v)
      if (Number.isInteger(qty) && qty > 0 && qty <= 99) out[k] = qty
    }
    return out
  } catch { return {} }
}
const cart = ref(loadCart())
function saveCart() { localStorage.setItem(CART_KEY, JSON.stringify(cart.value)) }
function cartQty(id) { return cart.value[id] || 0 }

const menuItems = computed(() => items.value.filter((r) => r.on_menu))
const ordered = computed(() =>
  menuItems.value
    .map((r) => ({ ...r, qty: cartQty(r.id) }))
    .filter((r) => r.qty > 0)
)
const orderedCount = computed(() => ordered.value.length)
const totalPrice = computed(() => {
  const sum = ordered.value.reduce((s, r) => s + (r.menu_price ?? 0) * r.qty, 0)
  return sum || null
})
const hasUnpriced = computed(() => ordered.value.some((r) => r.menu_price == null))

const activeCat = ref('全部')
const categories = computed(() => {
  const seen = []
  for (const r of menuItems.value) {
    if (r.menu_category && !seen.includes(r.menu_category)) seen.push(r.menu_category)
  }
  return seen
})
const filtered = computed(() => {
  const list = activeCat.value === '全部'
    ? [...menuItems.value]
    : menuItems.value.filter((r) => r.menu_category === activeCat.value)
  return list.sort((a, b) => {
    const qa = cartQty(a.id) > 0
    const qb = cartQty(b.id) > 0
    if (qa !== qb) return qa ? -1 : 1
    return new Date(b.menu_at || 0) - new Date(a.menu_at || 0)
  })
})

const todayText = new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' })

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

function changeQty(r, delta) {
  const qty = Math.min(99, Math.max(0, cartQty(r.id) + delta))
  const next = { ...cart.value }
  if (qty > 0) next[r.id] = qty
  else delete next[r.id]
  cart.value = next
  saveCart()
  if (delta > 0) {
    justAdded.value = r.id
    clearTimeout(addedTimer)
    addedTimer = setTimeout(() => { justAdded.value = null }, 500)
  }
}

function clearAll() {
  cart.value = {}
  saveCart()
}

const personName = ref(localStorage.getItem('foodie_order_person') || '')
const submitting = ref(false)
const orderDone = ref(false)
const orderDoneMsg = ref('')

// ---- 订单进度 ----
const STATUS_STEPS = ['已下单', '制作中', '已上菜']
const STATUS_INDEX = { pending: 0, making: 1, served: 2 }
const orderStatus = ref(null)
const statusPct = computed(() => ((STATUS_INDEX[orderStatus.value?.status] ?? 0) + 1) / 3 * 100)
let statusTimer = null
const statusIndex = computed(() => STATUS_INDEX[orderStatus.value?.status] ?? 0)

async function pollOrderStatus(orderId) {
  try {
    const o = await api.getOrder(orderId)
    orderStatus.value = o
    if (o.status === 'served' || new Date(o.created_at).getTime() < Date.now() - 2 * 3600 * 1000) {
      stopPolling()
    }
  } catch {
    stopPolling()
  }
}

function startPolling(orderId) {
  stopPolling()
  pollOrderStatus(orderId)
  statusTimer = setInterval(() => pollOrderStatus(orderId), 8000)
}

function stopPolling() {
  if (statusTimer) { clearInterval(statusTimer); statusTimer = null }
}

function resumeLastOrder() {
  try {
    const lo = JSON.parse(localStorage.getItem('foodie_last_order') || 'null')
    if (lo && lo.id && Date.now() - (lo.ts || 0) < 2 * 3600 * 1000) {
      startPolling(lo.id)
    }
  } catch { /* 忽略 */ }
}

// ---- 撒花 ----
const confettiEl = ref(null)
const confettiOn = ref(false)
let confettiRaf = null

watch(() => orderStatus.value?.status, (s) => {
  if (s === 'served') fireConfetti()
})

function fireConfetti() {
  const el = confettiEl.value
  if (!el) return
  confettiOn.value = true
  nextTick(() => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const w = window.innerWidth, h = window.innerHeight
    el.width = w * dpr; el.height = h * dpr
    const ctx = el.getContext('2d')
    ctx.scale(dpr, dpr)
    const colors = ['#f06a4f', '#ffb199', '#f5a623', '#4caf7d', '#5b9bd5', '#c880e0']
    const ps = Array.from({ length: 90 }, () => ({
      x: w / 2 + (Math.random() - 0.5) * w * 0.7,
      y: h * 0.3 + Math.random() * h * 0.2,
      vx: (Math.random() - 0.5) * 7,
      vy: -Math.random() * 8 - 3,
      s: Math.random() * 7 + 4,
      c: colors[(Math.random() * colors.length) | 0],
      r: Math.random() * Math.PI,
      vr: (Math.random() - 0.5) * 0.3,
    }))
    const t0 = performance.now()
    const tick = (t) => {
      ctx.clearRect(0, 0, w, h)
      const dt = Math.min((t - t0) / 1000, 3)
      for (const p of ps) {
        p.vy += 0.18; p.x += p.vx; p.y += p.vy; p.r += p.vr
        ctx.save()
        ctx.translate(p.x, p.y); ctx.rotate(p.r)
        ctx.fillStyle = p.c
        ctx.globalAlpha = Math.max(0, 1 - dt / 2.6)
        ctx.fillRect(-p.s / 2, -p.s / 2, p.s, p.s * 0.62)
        ctx.restore()
      }
      if (dt < 2.8) confettiRaf = requestAnimationFrame(tick)
      else { confettiOn.value = false }
    }
    confettiRaf = requestAnimationFrame(tick)
  })
}

async function submitOrder() {
  if (!ordered.value.length) { cartOpen.value = false; return }
  submitting.value = true
  error.value = ''
  try {
    localStorage.setItem('foodie_order_person', personName.value.trim())
    const payload = {
      person: personName.value.trim() || null,
      items: ordered.value.map((r) => ({ recipe_id: r.id, qty: r.qty })),
    }
    const order = await api.createOrder(payload)
    clearAll()
    load()
    localStorage.setItem('foodie_last_order', JSON.stringify({ id: order.id, ts: Date.now() }))
    startPolling(order.id)
    const names = order.items.slice(0, 3).map((i) => i.title).join('、')
    orderDone.value = true
    orderDoneMsg.value = `${order.items.length} 道菜 · ¥${order.total}${names ? '（' + names + (order.items.length > 3 ? '…' : '') + '）' : ''}`
    setTimeout(() => { orderDone.value = false }, 6000)
  } catch (e) {
    error.value = e.message
    load()
  } finally {
    submitting.value = false
  }
}

onMounted(() => { load(); resumeLastOrder() })
onBeforeUnmount(() => { stopPolling(); clearTimeout(addedTimer); if (confettiRaf) cancelAnimationFrame(confettiRaf) })
</script>

<style scoped>
/* ============ 点餐页 · 炫酷版 ============ */
.order-page {
  min-height: 100vh;
  background:
    radial-gradient(900px 500px at 85% -80px, rgba(240, 106, 79, 0.14), transparent 60%),
    radial-gradient(700px 400px at -15% 30%, rgba(245, 166, 35, 0.10), transparent 60%),
    #faf7f3;
  max-width: 520px; margin: 0 auto;
  position: relative;
}

/* ---- Hero ---- */
.hero {
  position: relative; overflow: hidden;
  background: linear-gradient(135deg, #f4704f 0%, #e5533c 52%, #d43a2a 100%);
  border-radius: 0 0 30px 30px;
  padding: 26px 20px 42px;
  color: #fff;
  box-shadow: 0 14px 34px rgba(229, 83, 60, 0.32);
}
.blob {
  position: absolute; border-radius: 50%;
  filter: blur(46px); opacity: 0.55; pointer-events: none;
  animation: blob-float 9s ease-in-out infinite alternate;
}
.blob-a { width: 220px; height: 220px; background: rgba(255, 214, 145, 0.85); top: -60px; left: -50px; }
.blob-b { width: 180px; height: 180px; background: rgba(255, 122, 88, 0.8); bottom: -70px; right: -30px; animation-delay: -4.5s; }
@keyframes blob-float { from { transform: translate(0, 0) scale(1); } to { transform: translate(26px, 14px) scale(1.14); } }
.hero-inner { position: relative; display: flex; align-items: center; gap: 14px; }
.hero-mark {
  width: 54px; height: 54px; border-radius: 18px; flex: none;
  background: rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.35);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}
.hero-title h1 { font-size: 26px; font-weight: 800; letter-spacing: 1px; text-shadow: 0 2px 8px rgba(0, 0, 0, 0.14); }
.hero-title p { font-size: 12.5px; opacity: 0.92; margin-top: 3px; }
.hero-badge {
  margin-left: auto; flex: none;
  background: rgba(255, 255, 255, 0.92); color: #c9442e;
  font-size: 12px; font-weight: 800;
  border-radius: 14px; padding: 4px 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.14);
  animation: hero-pop 0.3s ease;
}
@keyframes hero-pop { 0% { transform: scale(0.7); } 70% { transform: scale(1.08); } 100% { transform: scale(1); } }

/* ---- 分类栏 ---- */
.cat-bar {
  position: sticky; top: 10px; z-index: 30;
  display: flex; gap: 8px; overflow-x: auto;
  padding: 10px 16px; margin: -22px 0 6px;
  scrollbar-width: none;
}
.cat-bar::-webkit-scrollbar { display: none; }
.cat-tab {
  flex: none; background: #fff; color: #7a6a58;
  border: 1px solid rgba(240, 235, 228, 0.9); border-radius: 18px;
  padding: 7px 16px; font-size: 13.5px; font-weight: 600;
  box-shadow: 0 3px 10px rgba(93, 63, 41, 0.08);
  transition: transform 0.15s, background 0.2s, color 0.2s, box-shadow 0.2s;
}
.cat-tab.on {
  background: var(--brand-grad); color: #fff; border-color: transparent;
  box-shadow: 0 6px 16px rgba(229, 83, 60, 0.38);
  transform: translateY(-1px);
}

.content { padding: 0 14px 118px; }

/* ---- 菜品列表 ---- */
.dish-list { display: flex; flex-direction: column; gap: 12px; }
.dish-row {
  display: flex; gap: 13px;
  background: #fff; border-radius: 20px; padding: 13px;
  box-shadow: var(--shadow-sm);
  border: 1.5px solid rgba(240, 235, 228, 0.7);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.2s;
  animation: rise 0.5s ease both;
  animation-delay: calc(var(--i) * 55ms);
}
@keyframes rise { from { opacity: 0; transform: translateY(16px) scale(0.98); } to { opacity: 1; transform: none; } }
.dish-row.ordered { border-color: rgba(229, 83, 60, 0.45); background: #fffaf7; box-shadow: 0 8px 20px rgba(229, 83, 60, 0.10); }

.dish-img-wrap { position: relative; width: 92px; height: 92px; flex: none; }
.dish-img {
  width: 100%; height: 100%; border-radius: 16px; object-fit: cover;
  display: block;
  box-shadow: 0 4px 10px rgba(93, 63, 41, 0.16);
}
.dish-img.fallback { background: #f5efe8; display: flex; align-items: center; justify-content: center; font-size: 30px; }
.dish-cat {
  position: absolute; left: 6px; bottom: 6px;
  font-size: 10px; font-weight: 700; color: #fff;
  background: rgba(28, 24, 20, 0.5);
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
  border-radius: 8px; padding: 2px 7px;
}

.dish-info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.dish-info h3 { font-size: 16px; font-weight: 700; color: #2f2a24; margin-bottom: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dish-meta { display: flex; align-items: center; gap: 4px; color: #a8937c; font-size: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.price-row { margin-top: auto; display: flex; align-items: center; justify-content: space-between; }
.price { font-size: 20px; font-weight: 800; color: var(--brand-deep); }
.price i { font-style: normal; font-size: 13px; margin-right: 1px; }
.price.unset { font-size: 14px; color: #a08d7a; font-weight: 600; }

/* 数量控件 */
.qty-ctrl { display: flex; align-items: center; gap: 8px; }
.qty-btn {
  width: 30px; height: 30px; border-radius: 50%;
  padding: 0; font-size: 15px; line-height: 1;
  position: relative; overflow: hidden;
  display: inline-flex; align-items: center; justify-content: center;
  transition: transform 0.12s ease;
}
.qty-btn:active { transform: scale(0.82); }
.qty-btn.plus { background: var(--brand-grad); color: #fff; box-shadow: 0 4px 12px rgba(229, 83, 60, 0.4); }
.qty-btn.minus { background: #fff; color: var(--brand); border: 1.5px solid rgba(229, 83, 60, 0.5); }
.qty-num { min-width: 20px; text-align: center; font-size: 15px; font-weight: 800; color: #2f2a24; }
.pop { display: inline-block; animation: num-pop 0.28s ease; }
@keyframes num-pop { 0% { transform: scale(1.5); } 60% { transform: scale(0.92); } 100% { transform: scale(1); } }
.ripple {
  position: absolute; inset: 0;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 50%;
  animation: ripple 0.45s ease-out forwards;
}
@keyframes ripple { from { transform: scale(0.4); opacity: 0.9; } to { transform: scale(2.4); opacity: 0; } }

/* ---- 底部购物车悬浮条 ---- */
.order-bar {
  position: fixed; z-index: 60;
  left: 50%; transform: translateX(-50%);
  bottom: calc(16px + env(safe-area-inset-bottom));
  width: min(492px, calc(100vw - 28px));
  background: linear-gradient(100deg, #2b241e, #40342a);
  color: #f5efe6;
  padding: 12px 16px;
  border-radius: 26px;
  display: flex; align-items: center; gap: 12px;
  cursor: pointer;
  box-shadow: 0 14px 36px rgba(43, 36, 30, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: transform 0.2s ease, box-shadow 0.2s;
}
.order-bar:active { transform: translateX(-50%) scale(0.985); }
.cart-icon {
  position: relative; flex: none;
  width: 46px; height: 46px; border-radius: 50%;
  background: rgba(255, 255, 255, 0.1); color: #b9a993;
  display: flex; align-items: center; justify-content: center;
}
.cart-icon.on { background: var(--brand-grad); color: #fff; box-shadow: 0 4px 12px rgba(229, 83, 60, 0.5); }
.cart-badge {
  position: absolute; top: -4px; right: -4px;
  min-width: 20px; height: 20px; padding: 0 5px;
  background: #f5a623; color: #fff;
  border-radius: 10px; font-size: 11px; font-weight: 800;
  display: flex; align-items: center; justify-content: center;
  border: 2px solid #2b241e;
}
.order-summary { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.summary-title { font-size: 13.5px; color: #d9c9b2; }
.summary-total { font-size: 15px; font-weight: 800; color: #fff; }
.summary-total b { color: #ffb199; font-size: 19px; font-weight: 800; }
.cart-empty { color: #9c8d78; font-size: 13.5px; }
.cart-arrow { color: #b9a993; transform: rotate(90deg); }

/* ---- 购物车弹层（底部抽屉） ---- */
.sheet-enter-active, .sheet-leave-active { transition: transform 0.28s cubic-bezier(0.32, 0.72, 0.25, 1); }
.sheet-enter-from, .sheet-leave-to { transform: translateY(100%); }
.cart-panel {
  position: fixed; left: 50%; transform: translateX(-50%);
  bottom: 0; z-index: 61;
  width: min(520px, 100vw);
  background: #fff; border-radius: 26px 26px 0 0;
  max-height: 78vh; overflow-y: auto;
  padding: 12px 16px calc(16px + env(safe-area-inset-bottom));
  box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.2);
  display: flex; flex-direction: column;
}
.sheet-handle { width: 42px; height: 5px; border-radius: 3px; background: #e5dcd0; margin: 0 auto 10px; }
.cart-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.cart-head h3 { font-size: 17px; font-weight: 800; color: #2f2a24; }
.clear-btn { display: inline-flex; align-items: center; gap: 4px; }
.cart-empty-list { text-align: center; padding: 24px 0; }
.cart-item { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px dashed var(--line); }
.cart-thumb { width: 50px; height: 50px; border-radius: 14px; object-fit: cover; flex: none; box-shadow: 0 3px 8px rgba(93, 63, 41, 0.14); }
.cart-thumb.fallback { background: #f5efe8; display: flex; align-items: center; justify-content: center; font-size: 22px; }
.cart-item-info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.cart-name { font-size: 14.5px; font-weight: 700; color: #2f2a24; }
.cart-total { text-align: right; padding: 12px 0 6px; font-size: 15px; color: #666; }
.cart-total b { color: var(--brand-deep); font-size: 20px; font-weight: 800; }
.cart-submit { display: flex; gap: 10px; margin-top: 8px; }
.person-input { flex: 1; font-size: 15px; padding: 11px 14px; border-radius: 14px; }
.submit-btn {
  flex: none; min-width: 138px; font-size: 15px; font-weight: 800;
  background: var(--brand-grad);
  border-radius: 14px;
  display: inline-flex; align-items: center; justify-content: center; gap: 5px;
  box-shadow: 0 6px 16px rgba(229, 83, 60, 0.36);
  position: relative; overflow: hidden;
}
.submit-btn.shine::after {
  content: ''; position: absolute; top: 0; left: -70%;
  width: 45%; height: 100%;
  background: linear-gradient(100deg, transparent, rgba(255, 255, 255, 0.45), transparent);
  transform: skewX(-18deg);
  animation: shine 2.8s ease-in-out infinite;
}
@keyframes shine { 0% { left: -70%; } 55% { left: 130%; } 100% { left: 130%; } }
.order-done { color: #2e7d32; background: #e8f5e9; border-radius: 10px; padding: 8px 12px; font-size: 13.5px; margin-top: 10px; }

/* 进度条 */
.status-card {
  margin-top: 10px; background: #fff8f1; border: 1px solid #f5d9c0;
  border-radius: 16px; padding: 12px 14px;
}
.status-track {
  position: relative; display: flex; justify-content: space-between;
  padding: 4px 2px 0;
}
.status-fill {
  position: absolute; top: 9px; left: 14px; right: 14px; height: 4px;
  background: var(--brand-grad); border-radius: 2px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0.35;
}
.status-step {
  position: relative; z-index: 1; flex: 1; text-align: center;
  font-size: 12px; font-weight: 700; color: #b8a898;
  display: flex; flex-direction: column; align-items: center; gap: 6px;
}
.status-step .dot {
  width: 12px; height: 12px; border-radius: 50%;
  background: #e8dfd2; border: 2px solid #fff;
  box-shadow: 0 0 0 2px #e8dfd2;
  transition: background 0.3s, box-shadow 0.3s;
}
.status-step.on { color: var(--brand-deep); }
.status-step.on .dot { background: var(--brand); box-shadow: 0 0 0 2px rgba(229, 83, 60, 0.28); }
.status-step.pulse .dot { animation: dot-pulse 1.2s ease-in-out infinite; }
@keyframes dot-pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.45); } }
.status-hint { margin-top: 8px; font-size: 12px; color: #8a6d52; text-align: center; }
.cart-close { width: 100%; background: #f3ede5; color: #6b5d4e; margin-top: 8px; border-radius: 12px; }

/* 撒花 */
.confetti { position: fixed; inset: 0; z-index: 200; pointer-events: none; }

@media (max-width: 768px) {
  .hero { padding: 20px 16px 36px; border-radius: 0 0 24px 24px; }
  .hero-title h1 { font-size: 22px; }
  .cat-bar { top: 8px; padding: 10px 12px; margin: -20px 0 4px; }
  .content { padding: 0 10px 112px; }
  .dish-row { padding: 11px; gap: 11px; }
  .dish-img-wrap { width: 84px; height: 84px; }
  .dish-info h3 { font-size: 15px; }
}
</style>
