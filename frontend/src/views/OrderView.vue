<template>
  <div class="order-page">
    <header class="order-head">
      <h1>📋 食集菜单</h1>
      <p class="muted">{{ menuItems.length }} 道菜</p>
    </header>

    <nav v-if="categories.length" class="cat-bar">
      <button
        v-for="c in ['全部', ...categories]" :key="c"
        class="cat-tab"
        :class="{ on: activeCat === c }"
        @click="activeCat = c"
      >{{ c }}</button>
    </nav>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-else-if="loading && !menuItems.length" class="empty">加载中…</div>
    <div v-else-if="!menuItems.length" class="empty menu-empty">
      菜单还没准备好
      <p class="muted">请稍后再来～</p>
    </div>

    <div v-else-if="!filtered.length" class="empty menu-empty">这个分类还没有菜</div>

    <div v-else class="dish-list">
      <div
        v-for="r in filtered" :key="r.id"
        class="dish-row"
        :class="{ ordered: cartQty(r.id) > 0 }"
      >
        <img v-if="r.cover_image" :src="mediaUrl(r.cover_image)" class="dish-img" alt="" loading="lazy" decoding="async" />
        <span v-else class="dish-img fallback">🍳</span>
        <div class="dish-info">
          <h3>{{ r.title }}</h3>
          <div class="dish-meta">
            <span v-if="r.cooking_time_min" class="muted">⏱ {{ r.cooking_time_min }} 分钟</span>
            <span v-if="r.servings" class="muted">· {{ r.servings }}</span>
          </div>
          <div class="price-row">
            <span class="price" :class="{ unset: r.menu_price == null }">{{ r.menu_price != null ? `¥${r.menu_price}` : '时价' }}</span>
            <!-- 美团式数量控件 -->
            <div class="qty-ctrl">
              <button v-if="cartQty(r.id) > 0" class="qty-btn minus" @click="changeQty(r, -1)">－</button>
              <span v-if="cartQty(r.id) > 0" class="qty-num">{{ cartQty(r.id) }}</span>
              <button class="qty-btn plus" @click="changeQty(r, 1)">＋</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部购物车栏 -->
    <div class="order-bar" :class="{ active: cartOpen }" @click="cartOpen = true">
      <div class="cart-icon" :class="{ on: orderedCount }">🛒</div>
      <div class="order-summary">
        <template v-if="orderedCount">
          <span>已点 <b>{{ orderedCount }}</b> 道 / {{ totalQty }} 份</span>
          <span v-if="totalPrice" class="total">合计 <b>¥{{ totalPrice }}</b></span>
        </template>
        <span v-else class="cart-empty">还没有点菜，逛逛菜单吧</span>
      </div>
      <span class="cart-arrow">{{ cartOpen ? '▾' : '▴' }}</span>
    </div>

    <!-- 购物车弹层 -->
    <transition name="slide">
      <div v-if="cartOpen" class="cart-panel">
        <div class="cart-head">
          <h3>已点菜品</h3>
          <button class="ghost clear-btn" @click="clearAll">🗑 清空</button>
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
            <button class="qty-btn minus" @click.stop="changeQty(r, -1)">－</button>
            <span class="qty-num">{{ r.qty }}</span>
            <button class="qty-btn plus" @click.stop="changeQty(r, 1)">＋</button>
          </div>
        </div>
        <div v-if="totalPrice" class="cart-total">
          合计 <b>¥{{ totalPrice }}</b><span v-if="hasUnpriced" class="muted">（含时价菜）</span>
        </div>
        <div class="cart-submit">
          <input
            v-model="personName"
            class="person-input"
            placeholder="你的名字（可选）"
            @click.stop
          />
          <button class="submit-btn" :disabled="submitting" @click.stop="submitOrder">
            {{ submitting ? '下单中…' : (orderedCount ? '✔ 下单' : '去点菜') }}
          </button>
        </div>
        <p v-if="orderDone" class="order-done">✅ 已下单！{{ orderDoneMsg }}</p>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="cart-close" @click="cartOpen = false">收起 ▾</button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api, mediaUrl } from '../api'

const CART_KEY = 'foodie_cart_v1'
const items = ref([])
const error = ref('')
const loading = ref(false)
const cartOpen = ref(false)

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
const totalQty = computed(() => ordered.value.reduce((s, r) => s + r.qty, 0))
const totalPrice = computed(() => {
  const sum = ordered.value.reduce((s, r) => s + (r.menu_price ?? 0) * r.qty, 0)
  return sum || null
})
const hasUnpriced = computed(() => ordered.value.some((r) => r.menu_price == null))

// 已点的置顶，其余按上架时间
const activeCat = ref('全部')
// 分类（按菜单出现顺序）
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
}

function clearAll() {
  cart.value = {}
  saveCart()
}

const personName = ref(localStorage.getItem('foodie_order_person') || '')
const submitting = ref(false)
const orderDone = ref(false)
const orderDoneMsg = ref('')

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
    load() // 刷新菜单（价格/上架状态可能已变化）
    const names = order.items.slice(0, 3).map((i) => i.title).join('、')
    orderDone.value = true
    orderDoneMsg.value = `${order.items.length} 道菜 · ¥${order.total}${names ? '（' + names + (order.items.length > 3 ? '…' : '') + '）' : ''}`
    setTimeout(() => { orderDone.value = false }, 6000)
  } catch (e) {
    error.value = e.message
    load() // 菜单可能已变化（菜品下架等），同步最新状态
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.order-page { max-width: 640px; margin: 0 auto; }
.order-head { text-align: center; padding: 14px 0 16px; }
.order-head h1 { font-size: 21px; color: #2f2a24; }
.menu-empty { line-height: 2; }
.cat-bar {
  position: sticky; top: 0; z-index: 20;
  display: flex; gap: 8px; overflow-x: auto;
  padding: 8px 12px; margin: 0 -12px 10px;
  background: var(--bg); scrollbar-width: none;
}
.cat-bar::-webkit-scrollbar { display: none; }
.cat-tab {
  flex: none; background: #fff; color: #7a6a58;
  border: 1px solid var(--line); border-radius: 18px;
  padding: 5px 14px; font-size: 13.5px; font-weight: 600;
}
.cat-tab.on { background: var(--brand); color: #fff; border-color: var(--brand); }
.dish-list { display: flex; flex-direction: column; gap: 10px; padding: 0 12px 100px; }
.dish-row {
  display: flex; gap: 12px; align-items: stretch;
  background: #fff; border-radius: var(--radius); padding: 12px;
  box-shadow: var(--shadow-sm); border: 1px solid rgba(240, 235, 228, 0.6);
}
.dish-row.ordered { border-color: var(--brand); background: #fffaf7; }
.dish-img { width: 84px; height: 84px; border-radius: 10px; object-fit: cover; flex: none; }
.dish-img.fallback { background: #f5efe8; display: flex; align-items: center; justify-content: center; font-size: 30px; }
.dish-info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.dish-info h3 { font-size: 16px; font-weight: 700; color: #2f2a24; margin-bottom: 3px; }
.dish-meta { font-size: 12px; margin-bottom: 4px; }
.price-row { margin-top: auto; display: flex; align-items: center; justify-content: space-between; }
.price { font-size: 17px; font-weight: 800; color: var(--brand-deep); }
.price.unset { font-size: 14px; color: #a08d7a; font-weight: 600; }

/* 数量控件（美团式圆形 +/-） */
.qty-ctrl { display: flex; align-items: center; gap: 8px; }
.qty-btn {
  width: 26px; height: 26px; border-radius: 50%;
  padding: 0; font-size: 15px; line-height: 1;
  display: inline-flex; align-items: center; justify-content: center;
}
.qty-btn.plus { background: var(--brand); color: #fff; box-shadow: 0 2px 6px rgba(229, 83, 60, 0.35); }
.qty-btn.minus { background: #fff; color: var(--brand); border: 1.5px solid var(--brand); }
.qty-num { min-width: 18px; text-align: center; font-size: 15px; font-weight: 700; }

/* 底部购物车栏 */
.order-bar {
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 60;
  background: #2f2a24; color: #eee;
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  display: flex; align-items: center; gap: 12px;
  cursor: pointer;
}
.cart-icon {
  width: 44px; height: 44px; border-radius: 50%;
  background: rgba(255, 255, 255, 0.12); color: #888;
  display: flex; align-items: center; justify-content: center; font-size: 20px;
}
.cart-icon.on { background: var(--brand); color: #fff; }
.order-summary { flex: 1; font-size: 14px; display: flex; flex-direction: column; gap: 2px; }
.order-summary b { color: #fff; }
.total b { color: #ffb199; font-size: 16px; }
.cart-empty { color: #999; }
.cart-arrow { color: #bbb; font-size: 16px; }

/* 购物车弹层 */
.cart-panel {
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 61;
  background: #fff; border-radius: 18px 18px 0 0;
  max-height: 70vh; overflow-y: auto;
  padding: 16px 16px calc(16px + env(safe-area-inset-bottom));
  box-shadow: 0 -8px 30px rgba(0, 0, 0, 0.15);
}
.cart-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.cart-head h3 { font-size: 16px; color: #2f2a24; }
.cart-empty-list { text-align: center; padding: 20px 0; }
.cart-item { display: flex; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px dashed var(--line); }
.cart-thumb { width: 44px; height: 44px; border-radius: 8px; object-fit: cover; flex: none; }
.cart-thumb.fallback { background: #f5efe8; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.cart-item-info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.cart-name { font-size: 14px; font-weight: 600; color: #2f2a24; }
.cart-total { text-align: right; padding: 12px 0 8px; font-size: 15px; color: #666; }
.cart-submit { display: flex; gap: 10px; margin-top: 8px; }
.person-input { flex: 1; font-size: 15px; padding: 9px 12px; }
.submit-btn {
  flex: none; min-width: 110px; font-size: 15px; font-weight: 700;
  background: var(--brand-grad); box-shadow: 0 3px 10px rgba(229, 83, 60, 0.3);
}
.order-done { color: #2e7d32; background: #e8f5e9; border-radius: 8px; padding: 8px 12px; font-size: 13.5px; margin-top: 8px; }
.cart-total b { color: var(--brand-deep); font-size: 18px; }
.cart-close { width: 100%; background: #f3ede5; color: #6b5d4e; margin-top: 6px; }

.slide-enter-active, .slide-leave-active { transition: transform 0.22s ease; }
.slide-enter-from, .slide-leave-to { transform: translateY(100%); }

@media (max-width: 768px) {
  .dish-list { padding: 0 8px 100px; }
  .dish-img { width: 72px; height: 72px; }
  .dish-info h3 { font-size: 15px; }
}
</style>
