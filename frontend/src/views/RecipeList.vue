<template>
  <div>
    <div class="toolbar">
      <input
        v-model="searchText"
        class="search"
        placeholder="🔍 搜索菜名 / 食材 / 步骤…"
        @input="onSearchInput"
      />
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

    <div class="count muted">{{ total }} 个菜谱</div>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-else-if="loading && !items.length" class="empty">加载中…</div>
    <div v-else-if="!items.length" class="empty">
      {{ status === 'draft' ? '草稿箱是空的，去「导入」添加一个吧' : '还没有菜谱，去「导入」添加一个吧' }}
    </div>

    <div class="grid" v-else>
      <router-link
        v-for="r in items"
        :key="r.id"
        :to="`/recipe/${r.id}`"
        class="card recipe-card"
      >
        <div class="cover">
          <img v-if="r.cover_image" :src="mediaUrl(r.cover_image)" alt="" loading="lazy" decoding="async" />
          <span v-else class="cover-fallback">🍳</span>
          <span v-if="r.status === 'draft'" class="draft-badge">草稿</span>
          <button
            class="card-delete"
            :class="{ confirming: confirmDel === r.id }"
            :title="confirmDel === r.id ? '再点一次确认删除' : '删除'"
            @click.stop.prevent="askDelete(r)"
          >{{ confirmDel === r.id ? '确认？' : '🗑' }}</button>
        </div>
        <div class="body">
          <h3>{{ r.title }}</h3>
          <div class="meta">
            <span v-if="r.author" class="muted">{{ r.author }}</span>
            <span v-if="r.cooking_time_min" class="badge">⏱ {{ r.cooking_time_min }} 分钟</span>
            <span v-if="r.servings" class="badge">{{ r.servings }}</span>
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

async function removeRecipe(r) {
  try {
    await api.deleteRecipe(r.id)
    await load()
  } catch (e) {
    error.value = e.message
  }
}

const confirmDel = ref(null)
let confirmTimer = null
function askDelete(r) {
  if (confirmDel.value === r.id) {
    confirmDel.value = null
    clearTimeout(confirmTimer)
    removeRecipe(r)
    return
  }
  confirmDel.value = r.id
  clearTimeout(confirmTimer)
  confirmTimer = setTimeout(() => { confirmDel.value = null }, 3000)
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
.toolbar { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
.search { max-width: 420px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  background: #fff;
  color: #666;
  border: 1px solid #e5dfd8;
  border-radius: 20px;
  padding: 4px 14px;
  font-size: 13px;
}
.chip.active { background: #e5533c; color: #fff; border-color: #e5533c; }
.count { margin-bottom: 12px; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
.recipe-card { display: block; text-decoration: none; color: inherit; padding: 0; overflow: hidden; transition: transform 0.12s, box-shadow 0.12s; }
.recipe-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); }
.recipe-card:hover .cover img { transform: scale(1.06); }
.cover { position: relative; height: 150px; background: #f5efe8; display: flex; align-items: center; justify-content: center; }
.cover img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.35s ease; }
.cover-fallback { font-size: 40px; }
.draft-badge {
  position: absolute; top: 8px; left: 8px;
  background: #f5a623; color: #fff; font-size: 12px;
  border-radius: 10px; padding: 1px 8px;
}
.card-delete {
  position: absolute; top: 8px; right: 8px;
  background: rgba(0, 0, 0, 0.45); color: #fff;
  border-radius: 50%; width: 30px; height: 30px;
  padding: 0; font-size: 14px; line-height: 1;
  display: none; align-items: center; justify-content: center;
}
.recipe-card:hover .card-delete { display: inline-flex; }
.card-delete:hover { background: #d33; }
.card-delete.confirming { background: #d33; width: auto; border-radius: 14px; padding: 0 10px; font-size: 12px; display: inline-flex; }
.body { padding: 12px 14px; }
.body h3 { font-size: 15.5px; font-weight: 700; margin-bottom: 7px; color: #2f2a24; }
.meta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .cover { height: 96px; }
  .cover-fallback { font-size: 32px; }
  .body { padding: 8px 10px; }
  .body h3 { font-size: 14px; }
  /* 触屏没有 hover：删除按钮常显 */
  .card-delete { display: inline-flex; background: rgba(0, 0, 0, 0.45); width: 30px; height: 30px; }
  .recipe-card:hover .card-delete { display: inline-flex; }
}
</style>
