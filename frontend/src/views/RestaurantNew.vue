<template>
  <div>
    <h1 class="page-title">＋ 录入餐厅</h1>

    <!-- 按名字搜索添加 -->
    <div class="card search-card">
      <h2>🔍 按名字搜索添加</h2>
      <p class="muted">输入店名，自动从大众点评找到这家店（含封面/人均/评分/坐标），一键添加，通常几秒完成。</p>
      <div class="search-row">
        <input v-model="keyword" placeholder="如：泽厨记抓饭" class="kw" @keyup.enter="doSearch" />
        <button :disabled="searching" @click="doSearch">{{ searching ? '搜索中…' : '搜索' }}</button>
      </div>
      <div v-if="searchError" class="error">{{ searchError }}</div>

      <div v-if="results.length" class="results">
        <div v-for="shop in results" :key="shop.shop_uuid" class="poi-item">
          <img v-if="shop.cover_image" :src="shop.cover_image" class="poi-cover" alt="" />
          <span v-else class="poi-cover fallback">🍽</span>
          <div class="poi-info">
            <b>{{ shop.name }}</b>
            <span v-if="shop.cuisine" class="tag">{{ shop.cuisine }}</span>
            <span class="badge">¥{{ shop.price_per_person }}/人</span>
            <span v-if="shop.rating" class="badge">⭐ {{ shop.rating }}</span>
            <div v-if="shop.lat" class="muted">📍 有坐标（可算距离）</div>
            <div class="muted addr">{{ shop.address || '' }}</div>
          </div>
          <button class="secondary" :disabled="adding === shop.shop_uuid" @click="addShop(shop)">
            {{ adding === shop.shop_uuid ? '添加中…' : '＋ 添加' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 搜索不到时的兜底：粘贴大众点评链接 -->
    <div class="card search-card">
      <h2>🔗 从大众点评链接导入</h2>
      <p class="muted">按名字搜不到时，把店铺的大众点评链接粘贴到这里（如 https://m.dianping.com/shop/xxx），自动抓取信息后添加。</p>
      <div class="search-row">
        <input v-model="linkUrl" placeholder="https://m.dianping.com/shop/..." class="kw" @keyup.enter="doImport" />
        <button :disabled="importing" @click="doImport">{{ importing ? '导入中…' : '导入' }}</button>
      </div>
      <div v-if="importError" class="error">{{ importError }}</div>
    </div>

    <div class="divider"><span>或手动录入</span></div>

    <RestaurantEditor @saved="onSaved" @cancel="$router.push('/restaurants')" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import RestaurantEditor from '../components/RestaurantEditor.vue'

const router = useRouter()
const keyword = ref('')
const searching = ref(false)
const adding = ref('')
const searchError = ref('')
const results = ref([])
const linkUrl = ref('')
const importing = ref(false)
const importError = ref('')

async function doSearch() {
  if (!keyword.value.trim()) { searchError.value = '请输入店名'; return }
  searching.value = true
  searchError.value = ''
  importError.value = ''
  try {
    results.value = await api.searchShops(keyword.value.trim())
  } catch (e) { searchError.value = e.message } finally { searching.value = false }
}

async function doImport() {
  const url = linkUrl.value.trim()
  if (!url) { importError.value = '请粘贴大众点评链接'; return }
  importing.value = true
  importError.value = ''
  searchError.value = ''
  try {
    const shop = await api.syncDianping(url)
    results.value = [shop]  // 复用下方结果列表的"添加"按钮
  } catch (e) { importError.value = e.message } finally { importing.value = false }
}

async function addShop(shop) {
  adding.value = shop.shop_uuid
  searchError.value = ''
  try {
    const created = await api.createRestaurant({
      name: shop.name,
      cuisine: shop.cuisine,
      address: shop.address,
      lat: shop.lat,
      lng: shop.lng,
      price_per_person: shop.price_per_person,
      rating: shop.rating,
      cover_image: shop.cover_image,
      source_url: shop.source_url,
      source_shop_id: shop.shop_uuid,
      source_platform: 'dianping',
      tags: [],
      status: 'published',
    })
    // 后台自动同步推荐菜（不阻塞跳转）
    api.syncDishes(created.id).catch(() => {})
    router.push(`/restaurant/${created.id}`)
  } catch (e) {
    searchError.value = e.message
    adding.value = ''
  }
}

function onSaved() { router.push('/restaurants') }
</script>

<style scoped>
.page-title { font-size: 22px; margin-bottom: 14px; }
.search-card { margin-bottom: 14px; }
.search-card h2 { font-size: 17px; margin-bottom: 6px; color: #e5533c; }
.search-row { display: flex; gap: 8px; margin: 10px 0; }
.kw { flex: 1; }
.results { margin-top: 10px; }
.poi-item { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px dashed #eee; }
.poi-cover { width: 64px; height: 64px; border-radius: 8px; object-fit: cover; flex: none; }
.poi-cover.fallback { background: #f5efe8; display: flex; align-items: center; justify-content: center; font-size: 24px; }
.poi-info { flex: 1; min-width: 0; }
.poi-info b { font-size: 15px; margin-right: 8px; }
.addr { font-size: 12px; }
.divider { text-align: center; color: #bbb; font-size: 13px; margin: 16px 0; }
.divider span { background: #faf8f5; padding: 0 12px; }
.error { margin-top: 8px; }

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .poi-item { gap: 8px; }
  .poi-cover { width: 56px; height: 56px; }
  .poi-info b { font-size: 14px; margin-right: 6px; }
  .poi-item .badge, .poi-item .tag { font-size: 11px; padding: 1px 8px; }
}
</style>
