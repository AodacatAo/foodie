<template>
  <div v-if="error" class="error">{{ error }}</div>
  <div v-else-if="!recipe" class="empty">加载中…</div>
  <template v-else>
    <button class="ghost back" @click="$router.back()"><Icon name="back" :size="15" /> 返回</button>

    <div v-if="recipe.status === 'draft'" class="draft-banner">
      ⚠️ 这是导入生成的草稿，请核对内容后确认发布
      <div class="banner-actions">
        <button class="secondary" @click="editing = true">编辑</button>
        <button class="publish-btn" @click="publish"><Icon name="check" :size="15" /> 确认发布</button>
        <button class="secondary danger" :class="{ confirming: confirmDel === 'draft' }" @click="askDelete('draft')">
          {{ confirmDel === 'draft' ? '再点确认' : '删除' }}
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
      <!-- Hero 大图头 -->
      <div class="detail-hero" :class="{ 'has-cover': !!recipe.cover_image }">
        <img v-if="recipe.cover_image" :src="mediaUrl(recipe.cover_image)" class="hero-bg" alt="" />
        <div class="hero-overlay"></div>
        <div class="hero-content">
          <h1 class="hero-title">{{ recipe.title }}</h1>
          <div class="meta">
            <span v-if="recipe.author" class="glass-chip"><Icon name="bowl" :size="12" /> {{ recipe.author }}</span>
            <span v-if="recipe.cooking_time_min" class="glass-chip"><Icon name="clock" :size="12" /> {{ recipe.cooking_time_min }} 分钟</span>
            <span v-if="recipe.servings" class="glass-chip"><Icon name="servings" :size="12" /> {{ recipe.servings }}</span>
            <span v-if="recipe.source_url" class="glass-chip">
              <a :href="recipe.source_url" target="_blank" rel="noopener">来源 ↗</a>
            </span>
          </div>
          <div v-if="recipe.tags && recipe.tags.length" class="tags">
            <span v-for="t in recipe.tags" :key="t" class="glass-tag">{{ t }}</span>
          </div>
        </div>
      </div>

      <p v-if="recipe.description" class="desc">{{ recipe.description }}</p>
      <video v-if="recipe.video_path" :src="mediaUrl(recipe.video_path)" controls class="video-player"></video>

      <div v-if="recipe.status === 'published'" class="head-actions">
        <button class="action-btn" @click="makeShare"><Icon name="share" :size="15" /> 分享卡片</button>
        <button class="action-btn" @click="editing = true"><Icon name="edit" :size="15" /> 编辑</button>
        <button class="action-btn danger" :class="{ confirming: confirmDel === 'recipe' }" @click="askDelete('recipe')">
          <Icon name="trash" :size="15" /> {{ confirmDel === 'recipe' ? '再点确认' : '删除' }}
        </button>
      </div>

      <div class="columns">
        <div class="card col ingredients-card">
          <h2 class="col-title"><Icon name="bowl" :size="16" /> 食材</h2>
          <ul class="ingredients">
            <li v-for="(ing, i) in recipe.ingredients" :key="i" @click="toggleChecked(i)">
              <span class="check" :class="{ on: checked[i] }"><Icon name="check" :size="11" /></span>
              <span :class="{ done: checked[i] }">
                <b>{{ ing.name }}</b>
                <span v-if="ing.amount" class="muted"> {{ ing.amount }}</span>
                <span v-if="ing.note" class="ing-note">{{ ing.note }}</span>
              </span>
            </li>
          </ul>
          <p v-if="!recipe.ingredients.length" class="muted">暂无食材信息</p>
        </div>

        <div class="card col steps-card">
          <h2 class="col-title"><Icon name="menu" :size="16" /> 步骤</h2>
          <div class="step-timeline">
            <div v-for="s in recipe.steps" :key="s.order" class="step-node">
              <div class="step-dot">{{ s.order }}</div>
              <div class="step-content">
                <div class="step-title" v-if="s.title"><b>{{ s.title }}</b></div>
                <p>{{ s.description }}</p>
                <img v-if="s.image" :src="mediaUrl(s.image)" class="step-img" alt="" />
              </div>
            </div>
          </div>
          <p v-if="!recipe.steps.length" class="muted">暂无步骤信息</p>
        </div>
      </div>
    </template>

    <!-- 分享卡片弹窗 -->
    <div v-if="shareOpen" class="share-overlay" @click.self="shareOpen = false">
      <div class="share-card">
        <h3><Icon name="share" :size="17" /> 分享菜谱卡片</h3>
        <div v-if="shareLoading" class="empty">生成中…</div>
        <template v-else-if="sharePath">
          <img :src="mediaUrl(sharePath)" class="share-img" alt="分享卡片" />
          <p class="muted share-tip">手机上长按图片保存，微信发给家人；电脑上可右键另存</p>
          <a class="download-link" :href="mediaUrl(sharePath)" :download="`${recipe.title}-食集菜谱.png`"><Icon name="share" :size="14" /> 直接下载</a>
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
import Icon from '../components/Icon.vue'
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
.back { margin-bottom: 12px; display: inline-flex; align-items: center; gap: 5px; background: #fff; border: 1px solid var(--line); padding: 5px 12px; box-shadow: var(--shadow-sm); }

/* 草稿横幅 */
.draft-banner {
  background: linear-gradient(120deg, #fff3dc, #ffe8c4); border: 1px solid #f5c26b; color: #8a6100;
  border-radius: 16px; padding: 12px 16px; margin-bottom: 14px;
  display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  font-weight: 600;
}
.banner-actions { display: flex; gap: 8px; }
.publish-btn { background: var(--brand-grad); display: inline-flex; align-items: center; gap: 5px; box-shadow: 0 4px 12px rgba(229, 83, 60, 0.3); }

/* Hero */
.detail-hero {
  position: relative; overflow: hidden;
  border-radius: 24px;
  background: linear-gradient(135deg, #f4704f 0%, #e5533c 55%, #c9442e 100%);
  box-shadow: 0 14px 34px rgba(229, 83, 60, 0.24);
  margin-bottom: 14px;
}
.detail-hero.has-cover { box-shadow: 0 14px 34px rgba(93, 63, 41, 0.22); }
.hero-bg { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.hero-overlay { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(20, 12, 6, 0.12) 0%, rgba(20, 12, 6, 0.52) 100%); }
.hero-content { position: relative; padding: 96px 22px 20px; color: #fff; display: flex; flex-direction: column; gap: 10px; }
.hero-title { font-size: 26px; font-weight: 800; letter-spacing: 1px; text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3); }
.meta { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.glass-chip {
  display: inline-flex; align-items: center; gap: 4px;
  background: rgba(255, 255, 255, 0.2); color: #fff;
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.25);
  font-size: 12.5px; font-weight: 600;
  border-radius: 12px; padding: 3px 10px;
}
.glass-chip a { color: #fff; }
.tags { display: flex; gap: 6px; flex-wrap: wrap; }
.glass-tag {
  background: rgba(255, 255, 255, 0.16); color: #ffd7cb;
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px; padding: 2px 10px; font-size: 12px; font-weight: 600;
}
.desc {
  background: #fff; border: 1px solid var(--line);
  border-radius: 16px; padding: 14px 16px;
  color: #555; font-size: 14px; white-space: pre-wrap;
  margin-bottom: 12px; line-height: 1.8;
}
.video-player { width: 100%; max-width: 340px; border-radius: 16px; margin-bottom: 12px; box-shadow: var(--shadow-md); }

/* 操作按钮 */
.head-actions { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.action-btn {
  display: inline-flex; align-items: center; gap: 5px;
  background: #fff; border: 1px solid var(--line); color: #6b5d4e;
  padding: 8px 14px; border-radius: 12px; font-size: 14px; font-weight: 600;
  box-shadow: var(--shadow-sm);
  transition: transform 0.12s, box-shadow 0.12s, border-color 0.15s;
}
.action-btn:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); border-color: rgba(229, 83, 60, 0.4); color: var(--brand-deep); }
.action-btn.danger { color: #d33; }
.action-btn.danger:hover { border-color: rgba(221, 51, 51, 0.4); color: #d33; }
.confirming { background: #d33 !important; color: #fff !important; border-color: #d33 !important; }

/* 两栏内容 */
.columns { display: grid; grid-template-columns: 1fr 1.7fr; gap: 14px; }
@media (max-width: 760px) { .columns { grid-template-columns: 1fr; } }
.col-title { display: flex; align-items: center; gap: 6px; font-size: 17px; font-weight: 800; color: #2f2a24; margin-bottom: 12px; }
.col-title :deep(.icon) { color: var(--brand); }

/* 食材 */
.ingredients { list-style: none; }
.ingredients li {
  display: flex; gap: 9px; align-items: flex-start;
  padding: 9px 0; border-bottom: 1px dashed #eee; cursor: pointer;
}
.check {
  flex: none; width: 19px; height: 19px; border-radius: 6px; margin-top: 1px;
  border: 1.6px solid #d8ccbc; color: transparent;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.ingredients li:hover .check { border-color: var(--brand); }
.check.on { background: var(--brand-grad); border-color: transparent; color: #fff; }
.done { text-decoration: line-through; color: #aaa; }
.ing-note { color: #c98a00; font-size: 12px; margin-left: 6px; }

/* 步骤时间线 */
.step-timeline { position: relative; }
.step-node { display: flex; gap: 14px; position: relative; padding-bottom: 22px; }
.step-node::before {
  content: ''; position: absolute; left: 17px; top: 40px; bottom: 2px;
  width: 2px; background: linear-gradient(180deg, rgba(229, 83, 60, 0.35), rgba(229, 83, 60, 0.1));
}
.step-node:last-child::before { display: none; }
.step-dot {
  flex: none; width: 36px; height: 36px; border-radius: 50%;
  background: var(--brand-grad); color: #fff;
  font-size: 15px; font-weight: 800;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px rgba(229, 83, 60, 0.35);
  z-index: 1;
}
.step-content { flex: 1; min-width: 0; }
.step-title { font-size: 15px; margin-bottom: 3px; color: #2f2a24; }
.step-content p { white-space: pre-wrap; font-size: 14px; color: #444; line-height: 1.75; }
.step-img { margin-top: 8px; max-width: 100%; border-radius: 14px; box-shadow: var(--shadow-sm); transition: transform 0.2s; }
.step-img:hover { transform: scale(1.015); }

/* 分享卡片弹窗 */
.share-overlay {
  position: fixed; inset: 0; z-index: 150;
  background: rgba(30, 22, 14, 0.55);
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.share-card {
  background: #fff; border-radius: 20px; padding: 20px;
  max-width: 420px; width: 100%; max-height: 86vh; overflow-y: auto;
  display: flex; flex-direction: column; gap: 10px; align-items: center; text-align: center;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.28);
  animation: pop-in 0.25s ease;
}
@keyframes pop-in { from { opacity: 0; transform: scale(0.94); } to { opacity: 1; transform: scale(1); } }
.share-card h3 { display: flex; align-items: center; gap: 6px; font-size: 17px; color: #2f2a24; }
.share-img { width: 100%; border-radius: 12px; box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12); }
.share-tip { font-size: 12.5px; }
.download-link { display: inline-flex; align-items: center; gap: 5px; color: #e5533c; font-size: 14px; font-weight: 700; }

@media (max-width: 768px) {
  .hero-content { padding: 76px 16px 16px; }
  .hero-title { font-size: 22px; }
  .detail-hero { border-radius: 20px; }
  .back { padding: 4px 10px; }
}
</style>
