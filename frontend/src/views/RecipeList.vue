<template>
  <div class="list-page">
    <!-- 顶部横幅 -->
    <div class="strip">
      <div>
        <h1 class="strip-title">{{ status === 'draft' ? '草稿箱' : '菜谱库' }}</h1>
        <p class="strip-sub">{{ total }} 个菜谱 · 今天想做什么？</p>
      </div>
      <div class="strip-icon"><Icon name="bowl" :size="22" /></div>
    </div>

    <div class="toolbar">
      <div class="search-wrap">
        <Icon name="search" :size="16" />
        <input
          v-model="searchText"
          class="search"
          placeholder="搜索菜名 / 食材 / 步骤…"
          @input="onSearchInput"
        />
      </div>
      <div class="chips" v-if="tags.length">
        <button
          v-for="t in tags"
          :key="t"
          class="chip"
          :class="{ active: t === tagFilter }"
          @click="toggleTag(t)"
        >{{ t }}</button>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-else-if="loading && !items.length" class="grid">
      <div v-for="i in 6" :key="i" class="card recipe-card skel"> </div>
    </div>
    <div v-else-if="!items.length" class="empty">
      {{ status === 'draft' ? '草稿箱是空的，去「导入」添加一个吧' : '还没有菜谱，去「导入」添加一个吧' }}
    </div>

    <div class="grid" v-else>
      <router-link
        v-for="(r, i) in items"
        :key="r.id"
        :to="`/recipe/${r.id}`"
        class="card recipe-card"
        :style="{ '--i': i }"
      >
        <div class="cover">
          <img v-if="r.cover_image" :src="mediaUrl(r.cover_image)" alt="" loading="lazy" decoding="async" />
          <span v-else class="cover-fallback">🍳</span>
          <div class="cover-tags">
            <span v-if="r.status === 'draft'" class="pill draft-pill">草稿</span>
            <span v-if="r.on_menu" class="pill menu-pill">菜单中</span>
          </div>
          <button
            class="cover-action"
            :class="{ on: r.on_menu }"
            :title="r.on_menu ? '从菜单下架' : '上架到菜单'"
            @click.stop.prevent="toggleMenu(r)"
          ><Icon :name="r.on_menu ? 'close' : 'menu'" :size="14" /></button>
        </div>
        <div class="body">
          <h3>{{ r.title }}</h3>
          <div class="meta">
            <span v-if="r.author" class="muted">{{ r.author }}</span>
            <span v-if="r.cooking_time_min" class="meta-ic"><Icon name="clock" :size="13" /> {{ r.cooking_time_min }} 分钟</span>
            <span v-if="r.servings" class="meta-ic"><Icon name="servings" :size="13" /> {{ r.servings }}</span>
          </div>
          <div v-if="r.tags && r.tags.length">
            <span v-for="t in r.tags" :key="t" class="tag">{{ t }}</span>
          </div>
        </div>
      </router-link>
    </div>
  </div>
</template>



<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, mediaUrl } from '../api'
import Icon from '../components/Icon.vue'

const route = useRoute()
const router = useRouter()
const items = ref([])
const total = ref(0)
const tags = ref([])
const loading = ref(false)
const error = ref('')
const searchText = ref('')
const tagFilter = ref('')
const status = ref('published')

let debounceTimer = null

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page_size: 200 }
    if (route.query.q) params.q = route.query.q
    if (route.query.tag) params.tag = route.query.tag
    if (route.query.status) params.status = route.query.status
    const data = await api.listRecipes(params)
    items.value = data.items
    total.value = data.total
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function onSearchInput() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    router.replace({ query: { ...route.query, q: searchText.value || undefined } })
  }, 300)
}

function toggleTag(t) {
  tagFilter.value = tagFilter.value === t ? '' : t
  router.replace({ query: { ...route.query, tag: tagFilter.value || undefined } })
}

async function toggleMenu(r) {
  try {
    if (r.on_menu) {
      await api.takeOffMenu(r.id)
      r.on_menu = false
      r.menu_want = false
    } else {
      await api.putOnMenu(r.id)
      r.on_menu = true
    }
  } catch (e) {
    error.value = e.message
  }
}

watch(() => route.query, () => {
  searchText.value = route.query.q || ''
  tagFilter.value = route.query.tag || ''
  status.value = route.query.status || 'published'
  load()
})

onMounted(async () => {
  searchText.value = route.query.q || ''
  tagFilter.value = route.query.tag || ''
  status.value = route.query.status || 'published'
  load()
  try { tags.value = await api.listTags() } catch { /* ignore */ }
})

onBeforeUnmount(() => clearTimeout(debounceTimer))
</script>


<style scoped>
.list-page {
  background:
    radial-gradient(900px 500px at 85% -80px, rgba(240, 106, 79, 0.14), transparent 60%),
    radial-gradient(700px 400px at -15% 30%, rgba(245, 166, 35, 0.10), transparent 60%),
    var(--bg);
  min-height: 100vh;
  margin: -26px -20px -64px;
  padding: 26px 20px 70px;
}
/* 顶部横幅（柔和渐变条） */
.strip {
  display: flex; align-items: center; justify-content: space-between;
  background: linear-gradient(120deg, #fdeeea, #fdf3dc);
  border: 1px solid rgba(240, 229, 216, 0.9);
  border-radius: 20px;
  padding: 14px 20px;
  margin-bottom: 14px;
}
.strip-title { font-size: 20px; font-weight: 800; color: #2f2a24; }
.strip-sub { font-size: 12.5px; color: #a08d7a; margin-top: 3px; }
.strip-icon {
  width: 44px; height: 44px; border-radius: 14px; flex: none;
  background: var(--brand-grad); color: #fff;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 16px rgba(229, 83, 60, 0.3);
}
.toolbar { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
.search-wrap {
  display: flex; align-items: center; gap: 8px;
  background: #fff; border: 1.5px solid #e7e0d6;
  border-radius: 14px; padding: 0 14px;
  max-width: 440px;
  transition: border-color 0.15s, box-shadow 0.15s;
  color: #b8a893;
}
.search-wrap:focus-within { border-color: var(--brand); box-shadow: 0 0 0 3px rgba(229, 83, 60, 0.12); color: var(--brand); }
.search { border: none; padding: 10px 0; box-shadow: none !important; background: transparent; }
.search:focus { box-shadow: none !important; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  background: #fff; color: #7a6a58;
  border: 1px solid #e5dfd8; border-radius: 20px;
  padding: 4px 14px; font-size: 13px; font-weight: 600;
  transition: all 0.15s;
}
.chip:hover { border-color: rgba(229, 83, 60, 0.5); color: var(--brand-deep); }
.chip.active { background: var(--brand-grad); color: #fff; border-color: transparent; box-shadow: 0 4px 12px rgba(229, 83, 60, 0.3); }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.recipe-card { display: block; text-decoration: none; color: inherit; padding: 0; overflow: hidden; transition: transform 0.12s, box-shadow 0.12s; animation: rise 0.5s ease both; animation-delay: calc(var(--i) * 50ms); }
@keyframes rise { from { opacity: 0; transform: translateY(16px) scale(0.98); } to { opacity: 1; transform: none; } }
.recipe-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); }
.recipe-card:hover .cover img { transform: scale(1.06); }
.skel { height: 240px; position: relative; overflow: hidden; }
.skel::after {
  content: ''; position: absolute; inset: 0;
  background: var(--skeleton); background-size: 200% 100%;
  animation: shimmer 1.6s infinite;
}
.cover { position: relative; height: 150px; background: #f5efe8; display: flex; align-items: center; justify-content: center; }
.cover img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.35s ease; }
.cover-fallback { font-size: 40px; }
.cover-tags { position: absolute; top: 8px; left: 8px; display: flex; flex-direction: column; gap: 4px; align-items: flex-start; }
.pill {
  font-size: 11px; font-weight: 700; color: #fff; line-height: 1.4;
  border-radius: 9px; padding: 2px 8px;
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
}
.draft-pill { background: rgba(245, 166, 35, 0.9); }
.menu-pill { background: rgba(46, 125, 50, 0.82); }
.cover-action {
  position: absolute; top: 8px; right: 8px;
  width: 30px; height: 30px; padding: 0;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.42); color: #fff;
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
}
.cover-action:hover { opacity: 1; background: var(--brand); }
.cover-action.on { background: rgba(46, 125, 50, 0.9); }
.cover-action.on:hover { background: #1e6b22; }
.body { padding: 12px 14px; }
.body h3 { font-size: 15.5px; font-weight: 700; margin-bottom: 7px; color: #2f2a24; }
.meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }
.meta-ic { display: inline-flex; align-items: center; gap: 3px; color: #a08d7a; font-size: 12.5px; background: #f7f3ec; border-radius: 10px; padding: 2px 8px; }

@media (max-width: 768px) {
  .list-page { margin: -14px -12px -96px; padding: 14px 12px 100px; }
  .strip { padding: 12px 14px; border-radius: 16px; }
  .strip-title { font-size: 18px; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .cover { height: 96px; }
  .cover-fallback { font-size: 32px; }
  .body { padding: 8px 10px; }
  .body h3 { font-size: 14px; }
  .cover-action { width: 28px; height: 28px; }
  .skel { height: 170px; }
  .search-wrap { max-width: none; }
}
</style>
