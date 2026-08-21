<template>
  <div class="import-page">
    <!-- Hero 渐变头 -->
    <header class="hero">
      <div class="blob blob-a"></div>
      <div class="blob blob-b"></div>
      <div class="hero-inner">
        <div class="hero-mark"><Icon name="import" :size="24" /></div>
        <div class="hero-text">
          <h1 class="hero-title">菜谱导入</h1>
          <p class="hero-sub">小红书链接 / 手动粘贴，AI 自动提炼食材与步骤</p>
        </div>
      </div>
      <div class="hero-tabs">
        <button class="hero-tab" :class="{ on: tab === 'manual' }" @click="tab = 'manual'">
          <Icon name="draft" :size="14" /> 手动粘贴
        </button>
        <button class="hero-tab" :class="{ on: tab === 'xhs' }" @click="tab = 'xhs'">
          <Icon name="import" :size="14" /> 小红书链接
        </button>
      </div>
    </header>

    <div class="content">
      <div v-if="tab === 'manual'" class="card form-card">
        <div class="card-head">
          <h2>粘贴内容</h2>
          <span class="head-chip">自动提炼</span>
        </div>
        <p class="muted hint">
          粘贴小红书笔记的正文（图文菜谱可先对图片做OCR得到文字）。
          已配置 DeepSeek 时自动提炼食材 + 步骤；否则按编号行拆分，稍后在草稿页编辑。
        </p>
        <div class="field">
          <label>菜名（可选，留空自动推断）</label>
          <input v-model="manual.title" placeholder="如：可乐鸡翅" />
        </div>
        <div class="field">
          <label>笔记内容 *</label>
          <textarea v-model="manual.text" rows="10" placeholder="把小红书笔记的正文粘贴到这里…"></textarea>
        </div>
        <div class="actions">
          <button class="cta shine" :disabled="submitting" @click="submitManual">
            <Icon name="check" :size="16" /> {{ submitting ? '提交中…' : '生成草稿' }}
          </button>
        </div>
        <div v-if="manualError" class="error">{{ manualError }}</div>
        <div v-if="task && tab === 'manual'" class="task-status" :class="'st-' + task.status">
          <span class="dot"></span>
          任务 #{{ task.id }}：{{ taskLabel() }}
        </div>
      </div>

      <div v-else class="card form-card">
        <div class="card-head">
          <h2>链接导入</h2>
          <span class="head-chip">抓取 + OCR</span>
        </div>
        <p class="muted hint">
          粘贴小红书笔记链接，自动抓取正文与图片、OCR 识别并提炼步骤，生成草稿。需先完成浏览器登录
          （<code>scripts/xhs_login.py</code>）。
        </p>
        <div class="field">
          <label>笔记链接</label>
          <input v-model="xhsUrl" placeholder="https://www.xiaohongshu.com/explore/..." />
        </div>
        <div class="actions">
          <button class="cta shine" :disabled="submitting" @click="submitXhs">
            <Icon name="import" :size="16" /> {{ submitting ? '提交中…' : '抓取并提炼' }}
          </button>
        </div>
        <div v-if="xhsError" class="error">{{ xhsError }}</div>
        <div v-if="task && tab === 'xhs'" class="task-status" :class="'st-' + task.status">
          <span class="dot"></span>
          任务 #{{ task.id }}：{{ taskLabel() }}
        </div>
      </div>

      <div class="tips-card">
        <Icon name="clock" :size="15" />
        <p>图片较多时 OCR/视频转写需要几分钟，页面会自动刷新任务状态，完成后直接带你去看草稿。</p>
      </div>
    </div>
  </div>
</template>


<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'

const router = useRouter()
const tab = ref('manual')
const manual = ref({ title: '', text: '' })
const xhsUrl = ref('')
const submitting = ref(false)
const manualError = ref('')
const xhsError = ref('')
const task = ref(null)

let pollTimer = null
const STATUS_LABEL = {
  pending: '排队中…',
  running: '提炼中…',
  success: '完成 ✓',
  failed: '失败 ✗',
  needs_review: '需要人工处理',
}

const taskLabel = () => (task.value ? STATUS_LABEL[task.value.status] || task.value.status : '')

async function submitManual() {
  if (!manual.value.text.trim()) {
    manualError.value = '请先粘贴笔记内容'
    return
  }
  submitting.value = true
  manualError.value = ''
  try {
    task.value = await api.submitManual({
      title: manual.value.title || null,
      text: manual.value.text,
    })
    poll()
  } catch (e) {
    manualError.value = e.message
  } finally {
    submitting.value = false
  }
}

async function submitXhs() {
  if (!xhsUrl.value.trim()) {
    xhsError.value = '请先粘贴链接'
    return
  }
  submitting.value = true
  xhsError.value = ''
  try {
    task.value = await api.submitXhs(xhsUrl.value.trim())
    poll()
  } catch (e) {
    xhsError.value = e.message
  } finally {
    submitting.value = false
  }
}

function poll() {
  clearTimeout(pollTimer)
  pollTimer = setTimeout(async () => {
    try {
      task.value = await api.getTask(task.value.id)
    } catch { /* 忽略轮询错误 */ }
    if (task.value.status === 'success' && task.value.recipe_id) {
      router.push(`/recipe/${task.value.recipe_id}`)
      return
    }
    if (task.value.status === 'failed') {
      const msg = task.value.error || '导入失败'
      if (tab.value === 'xhs') xhsError.value = msg
      else manualError.value = msg
      return
    }
    poll()
  }, 1500)
}

onBeforeUnmount(() => clearTimeout(pollTimer))
</script>

<style scoped>
.import-page {
  background:
    radial-gradient(900px 500px at 85% -80px, rgba(240, 106, 79, 0.14), transparent 60%),
    radial-gradient(700px 400px at -15% 30%, rgba(245, 166, 35, 0.10), transparent 60%),
    var(--bg);
  min-height: 100vh;
  margin: -26px -20px -64px;
  padding: 26px 20px 70px;
}
.hero {
  position: relative; overflow: hidden;
  background: linear-gradient(135deg, #f4704f 0%, #e5533c 52%, #d43a2a 100%);
  border-radius: 24px;
  padding: 22px 22px 18px;
  color: #fff;
  box-shadow: 0 14px 34px rgba(229, 83, 60, 0.28);
  margin-bottom: 16px;
}
.blob { position: absolute; border-radius: 50%; filter: blur(46px); opacity: 0.55; pointer-events: none; animation: blob-float 9s ease-in-out infinite alternate; }
.blob-a { width: 220px; height: 220px; background: rgba(255, 214, 145, 0.85); top: -60px; left: -50px; }
.blob-b { width: 180px; height: 180px; background: rgba(255, 122, 88, 0.8); bottom: -70px; right: -30px; animation-delay: -4.5s; }
@keyframes blob-float { from { transform: translate(0, 0) scale(1); } to { transform: translate(26px, 14px) scale(1.14); } }
.hero-inner { position: relative; display: flex; align-items: center; gap: 14px; }
.hero-mark {
  width: 50px; height: 50px; border-radius: 16px; flex: none;
  background: rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.35);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}
.hero-title { font-size: 22px; font-weight: 800; letter-spacing: 1px; }
.hero-sub { font-size: 12.5px; opacity: 0.95; margin-top: 3px; }
.hero-tabs {
  position: relative; display: flex; gap: 6px; margin-top: 16px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 14px; padding: 4px;
}
.hero-tab {
  flex: 1; justify-content: center;
  background: transparent; color: rgba(255, 255, 255, 0.85);
  display: inline-flex; align-items: center; gap: 5px;
  border-radius: 10px; padding: 8px 10px;
  font-size: 13.5px; font-weight: 600;
  transition: background 0.2s, color 0.2s, box-shadow 0.2s;
}
.hero-tab.on { background: #fff; color: #c9442e; font-weight: 800; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.14); }

.content { display: flex; flex-direction: column; gap: 14px; }
.form-card { animation: rise 0.45s ease both; }
@keyframes rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.card-head h2 { font-size: 17px; font-weight: 800; color: #2f2a24; }
.head-chip {
  font-size: 11px; font-weight: 700; color: var(--brand-deep);
  background: var(--brand-soft); border-radius: 10px; padding: 2px 9px;
}
.hint { margin-bottom: 14px; line-height: 1.7; }
.hint code { background: #f3ede5; border-radius: 6px; padding: 1px 6px; font-size: 12px; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 13px; color: #888; margin-bottom: 5px; font-weight: 600; }
.actions { margin-top: 2px; }
.cta {
  width: 100%; display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  background: var(--brand-grad);
  padding: 11px 16px; font-size: 15px; font-weight: 800;
  border-radius: 14px;
  box-shadow: 0 6px 16px rgba(229, 83, 60, 0.34);
  position: relative; overflow: hidden;
}
.cta.shine::after {
  content: ''; position: absolute; top: 0; left: -70%;
  width: 45%; height: 100%;
  background: linear-gradient(100deg, transparent, rgba(255, 255, 255, 0.45), transparent);
  transform: skewX(-18deg);
  animation: shine 2.8s ease-in-out infinite;
}
@keyframes shine { 0% { left: -70%; } 55% { left: 130%; } 100% { left: 130%; } }
.error { margin-top: 12px; }

/* 任务状态 */
.task-status {
  margin-top: 12px; display: inline-flex; align-items: center; gap: 7px;
  font-size: 13px; font-weight: 600; color: #7a6a58;
  background: #f7f3ec; border-radius: 12px; padding: 5px 12px;
}
.task-status .dot { width: 8px; height: 8px; border-radius: 50%; background: #b8ab9c; }
.task-status.st-running { color: #c97900; background: #fff3e0; }
.task-status.st-running .dot { background: #f5a623; animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.5); opacity: 0.6; } }
.task-status.st-success { color: #2e7d32; background: #e8f5e9; }
.task-status.st-success .dot { background: #2e7d32; }
.task-status.st-failed { color: #d33; background: #fdecec; }
.task-status.st-failed .dot { background: #d33; }

/* 提示条 */
.tips-card {
  display: flex; gap: 10px; align-items: flex-start;
  background: linear-gradient(120deg, #fdf3dc, #fdeeea);
  border: 1px solid rgba(240, 229, 216, 0.9);
  border-radius: 16px; padding: 12px 14px;
  color: #8a6d52; font-size: 12.5px; line-height: 1.7;
  animation: rise 0.45s ease 0.1s both;
}
.tips-card :deep(.icon) { margin-top: 2px; color: #c98a00; }

@media (max-width: 768px) {
  .import-page { margin: -14px -12px -96px; padding: 14px 12px 100px; }
  .hero { padding: 18px 16px 14px; border-radius: 20px; }
  .hero-title { font-size: 20px; }
}
</style>
