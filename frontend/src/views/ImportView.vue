<template>
  <div>
    <div class="tabs">
      <button :class="{ active: tab === 'manual' }" @click="tab = 'manual'">📝 手动录入</button>
      <button :class="{ active: tab === 'xhs' }" @click="tab = 'xhs'">🔗 小红书链接</button>
    </div>

    <div v-if="tab === 'manual'" class="card">
      <h2>手动录入笔记内容</h2>
      <p class="muted hint">
        粘贴小红书笔记的正文（图文菜谱可先对图片做OCR得到文字）。
        若已配置 DeepSeek API Key，将自动提炼为食材 + 步骤；否则按编号行拆分，稍后在草稿页编辑。
      </p>
      <div class="field">
        <label>菜名（可选，留空则自动推断）</label>
        <input v-model="manual.title" placeholder="如：可乐鸡翅" />
      </div>
      <div class="field">
        <label>笔记内容 *</label>
        <textarea v-model="manual.text" rows="10" placeholder="把小红书笔记的正文粘贴到这里…"></textarea>
      </div>
      <div class="actions">
        <button :disabled="submitting" @click="submitManual">
          {{ submitting ? '提交中…' : '🚀 生成草稿' }}
        </button>
      </div>
      <div v-if="manualError" class="error">{{ manualError }}</div>
      <div v-if="task" class="task-status muted">任务 #{{ task.id }}：{{ taskLabel() }}</div>
    </div>

    <div v-else class="card">
      <h2>从小红书链接导入</h2>
      <p class="muted hint">
        粘贴小红书笔记链接，自动抓取正文与图片、OCR 识别并提炼步骤，生成草稿。
        需先完成登录（<code>scripts/xhs_login.py</code>，登录态保存在本地浏览器配置目录）。
      </p>
      <div class="field">
        <label>笔记链接</label>
        <input v-model="xhsUrl" placeholder="https://www.xiaohongshu.com/explore/..." />
      </div>
      <div class="actions">
        <button :disabled="submitting" @click="submitXhs">{{ submitting ? '提交中…' : '抓取' }}</button>
      </div>
      <div v-if="xhsError" class="error">{{ xhsError }}</div>
      <div v-if="task" class="task-status muted">任务 #{{ task.id }}：{{ taskLabel() }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

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
.tabs { display: flex; gap: 8px; margin-bottom: 14px; }
.tabs button {
  background: #fff; color: #666; border: 1px solid #e5dfd8; padding: 8px 18px;
}
.tabs button.active { background: #e5533c; color: #fff; border-color: #e5533c; }
h2 { font-size: 18px; margin-bottom: 8px; }
.hint { margin-bottom: 16px; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 13px; color: #888; margin-bottom: 4px; }
.actions { margin-top: 4px; }
.error { margin-top: 12px; }
.task-status { margin-top: 12px; }

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .tabs button { flex: 1; padding: 10px 8px; }
}
</style>
