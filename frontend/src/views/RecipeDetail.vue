<template>
  <div v-if="error" class="error">{{ error }}</div>
  <div v-else-if="!recipe" class="empty">加载中…</div>
  <template v-else>
    <button class="ghost back" @click="$router.back()">← 返回</button>

    <div v-if="recipe.status === 'draft'" class="draft-banner">
      ⚠️ 这是导入生成的草稿，请核对内容后确认发布
      <div class="banner-actions">
        <button class="secondary" @click="editing = true">编辑</button>
        <button @click="publish">✓ 确认发布</button>
        <button class="secondary danger" :class="{ confirming: confirmDel === 'draft' }" @click="askDelete('draft')">
          {{ confirmDel === 'draft' ? '再点确认' : '🗑 删除' }}
        </button>
      </div>
    </div>

    <RecipeEditor
      v-if="editing"
      :recipe="recipe"
      @saved="onSaved"
      @cancel="editing = false"
    />

    <template v-else>
      <div class="card head">
        <h1>{{ recipe.title }}</h1>
        <div class="meta">
          <span v-if="recipe.author" class="badge">👩‍🍳 {{ recipe.author }}</span>
          <span v-if="recipe.cooking_time_min" class="badge">⏱ {{ recipe.cooking_time_min }} 分钟</span>
          <span v-if="recipe.servings" class="badge">🍽 {{ recipe.servings }}</span>
          <span v-if="recipe.source_url">
            <a :href="recipe.source_url" target="_blank" rel="noopener">来源链接 ↗</a>
          </span>
        </div>
        <div v-if="recipe.tags && recipe.tags.length">
          <span v-for="t in recipe.tags" :key="t" class="tag">{{ t }}</span>
        </div>
        <p v-if="recipe.description" class="desc">{{ recipe.description }}</p>
        <video
          v-if="recipe.video_path"
          :src="mediaUrl(recipe.video_path)"
          controls
          class="video-player"
        ></video>
        <div v-if="recipe.status === 'published'" class="head-actions">
          <button class="secondary" @click="makeShare">📤 分享卡片</button>
          <button class="secondary" @click="editing = true">✏️ 编辑</button>
          <button class="secondary danger" :class="{ confirming: confirmDel === 'recipe' }" @click="askDelete('recipe')">
            {{ confirmDel === 'recipe' ? '再点确认' : '🗑 删除' }}
          </button>
        </div>
      </div>

      <div class="columns">
        <div class="card col">
          <h2>食材</h2>
          <ul class="ingredients">
            <li v-for="(ing, i) in recipe.ingredients" :key="i" @click="toggleChecked(i)">
              <input type="checkbox" :checked="checked[i]" readonly />
              <span :class="{ done: checked[i] }">
                <b>{{ ing.name }}</b>
                <span v-if="ing.amount" class="muted"> {{ ing.amount }}</span>
                <span v-if="ing.note" class="ing-note">{{ ing.note }}</span>
              </span>
            </li>
          </ul>
          <p v-if="!recipe.ingredients.length" class="muted">暂无食材信息</p>
        </div>

        <div class="card col">
          <h2>步骤</h2>
          <ol class="steps">
            <li v-for="s in recipe.steps" :key="s.order" class="step">
              <div class="step-text">
                <div class="step-title" v-if="s.title"><b>{{ s.order }}. {{ s.title }}</b></div>
                <div v-else class="step-title"><b>{{ s.order }}.</b></div>
                <p>{{ s.description }}</p>
                <img v-if="s.image" :src="mediaUrl(s.image)" class="step-img" alt="" />
              </div>
            </li>
          </ol>
          <p v-if="!recipe.steps.length" class="muted">暂无步骤信息</p>
        </div>
      </div>
    </template>

    <!-- 分享卡片弹窗 -->
    <div v-if="shareOpen" class="share-overlay" @click.self="shareOpen = false">
      <div class="share-card">
        <h3>📤 分享菜谱卡片</h3>
        <div v-if="shareLoading" class="empty">生成中…</div>
        <template v-else-if="sharePath">
          <img :src="mediaUrl(sharePath)" class="share-img" alt="分享卡片" />
          <p class="muted share-tip">手机上长按图片保存，微信发给家人；电脑上可右键另存</p>
          <a class="download-link" :href="mediaUrl(sharePath)" :download="`${recipe.title}-食集菜谱.png`">💾 直接下载</a>
        </template>
        <p v-else-if="shareError" class="error">{{ shareError }}</p>
        <button class="secondary" @click="shareOpen = false">关闭</button>
      </div>
    </div>
  </template>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, mediaUrl } from '../api'
import RecipeEditor from '../components/RecipeEditor.vue'

const route = useRoute()
const router = useRouter()
const recipe = ref(null)
const error = ref('')
const editing = ref(false)
const checked = ref([])
const shareOpen = ref(false)
const shareLoading = ref(false)
const sharePath = ref('')
const shareError = ref('')

async function makeShare() {
  shareOpen.value = true
  shareLoading.value = true
  shareError.value = ''
  sharePath.value = ''
  try {
    const data = await api.makeShareCard(recipe.value.id)
    sharePath.value = data.path
  } catch (e) {
    shareError.value = e.message
  } finally {
    shareLoading.value = false
  }
}

async function load() {
  try {
    recipe.value = await api.getRecipe(route.params.id)
    checked.value = recipe.value.ingredients.map(() => false)
  } catch (e) {
    error.value = e.message
  }
}

function toggleChecked(i) {
  checked.value[i] = !checked.value[i]
}

async function publish() {
  try {
    await api.publishRecipe(recipe.value.id)
    await load()
  } catch (e) {
    error.value = e.message
  }
}

async function remove() {
  try {
    await api.deleteRecipe(recipe.value.id)
    router.push('/')
  } catch (e) {
    error.value = e.message
  }
}

const confirmDel = ref(null)
let confirmTimer = null
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

async function onSaved() {
  editing.value = false
  await load()
}

onMounted(load)
</script>

<style scoped>
.back { margin-bottom: 12px; }
.draft-banner {
  background: #fff7e6; border: 1px solid #f5c26b; color: #8a6100;
  border-radius: 10px; padding: 12px 16px; margin-bottom: 14px;
  display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
}
.banner-actions { display: flex; gap: 8px; }
.head { margin-bottom: 14px; }
.head h1 { font-size: 24px; margin-bottom: 8px; }
.meta { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
.meta a { color: #e5533c; font-size: 13px; }
.desc { margin-top: 10px; color: #555; white-space: pre-wrap; font-size: 14px; }
.video-player { width: 100%; max-width: 340px; border-radius: 10px; margin-top: 12px; }
.head-actions { margin-top: 12px; display: flex; gap: 8px; }
.danger { background: #fdecec; color: #d33; }
.confirming { background: #d33 !important; color: #fff !important; }
.columns { display: grid; grid-template-columns: 1fr 1.6fr; gap: 14px; }
@media (max-width: 760px) { .columns { grid-template-columns: 1fr; } }
.col h2 { font-size: 17px; margin-bottom: 12px; color: #e5533c; }
.ingredients { list-style: none; }
.ingredients li {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 8px 0; border-bottom: 1px dashed #eee; cursor: pointer;
}
.ingredients input { width: auto; margin-top: 4px; }
.done { text-decoration: line-through; color: #aaa; }
.ing-note { color: #c98a00; font-size: 12px; }
.steps { padding-left: 0; list-style: none; counter-reset: step; }
.step { display: flex; gap: 12px; padding: 12px 0; border-bottom: 1px dashed #eee; }
.step-title { font-size: 15px; margin-bottom: 4px; }
.step p { white-space: pre-wrap; font-size: 14px; color: #444; }
.step-img { margin-top: 8px; max-width: 100%; border-radius: 8px; }

/* 分享卡片弹窗 */
.share-overlay {
  position: fixed; inset: 0; z-index: 150;
  background: rgba(0, 0, 0, 0.6);
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.share-card {
  background: #fff; border-radius: 16px; padding: 20px;
  max-width: 420px; width: 100%; max-height: 86vh; overflow-y: auto;
  display: flex; flex-direction: column; gap: 10px; align-items: center; text-align: center;
}
.share-card h3 { font-size: 17px; color: #2f2a24; }
.share-img { width: 100%; border-radius: 10px; box-shadow: 0 6px 24px rgba(0,0,0,0.12); }
.share-tip { font-size: 12.5px; }
.download-link { color: #e5533c; font-size: 14px; font-weight: 600; }

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .head h1 { font-size: 20px; }
  .columns { grid-template-columns: 1fr; }
}
</style>
