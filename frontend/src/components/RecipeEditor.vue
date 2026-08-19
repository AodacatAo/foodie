<template>
  <div class="card">
    <h2>✏️ 编辑菜谱</h2>

    <div class="field">
      <label>标题 *</label>
      <input v-model="form.title" />
    </div>

    <div class="grid2">
      <div class="field">
        <label>作者</label>
        <input v-model="form.author" />
      </div>
      <div class="field">
        <label>来源链接</label>
        <input v-model="form.source_url" />
      </div>
      <div class="field">
        <label>耗时（分钟）</label>
        <input v-model.number="form.cooking_time_min" type="number" min="0" />
      </div>
      <div class="field">
        <label>份量</label>
        <input v-model="form.servings" placeholder="如：2人份" />
      </div>
    </div>

    <div class="field">
      <label>标签（逗号分隔）</label>
      <input v-model="tagsText" placeholder="如：川菜, 快手菜" />
    </div>

    <div class="field">
      <label>描述 / 小贴士</label>
      <textarea v-model="form.description" rows="3"></textarea>
    </div>

    <div class="field">
      <label>食材</label>
      <div v-for="(ing, i) in form.ingredients" :key="i" class="row">
        <input v-model="ing.name" placeholder="食材名" class="col-name" />
        <input v-model="ing.amount" placeholder="用量" class="col-amount" />
        <input v-model="ing.note" placeholder="备注" class="col-note" />
        <button class="ghost" @click="form.ingredients.splice(i, 1)">✕</button>
      </div>
      <button class="secondary" @click="form.ingredients.push({ name: '', amount: '', note: '' })">＋ 添加食材</button>
    </div>

    <div class="field">
      <label>步骤</label>
      <div v-for="(s, i) in form.steps" :key="i" class="row step-row">
        <span class="step-no">{{ i + 1 }}</span>
        <input v-model="s.title" placeholder="小标题（可选）" class="col-name" />
        <textarea v-model="s.description" placeholder="做法描述" rows="2" class="col-note"></textarea>
        <input v-model="s.image" placeholder="图片路径（可选）" class="col-name" />
        <button class="ghost" @click="form.steps.splice(i, 1)">✕</button>
      </div>
      <button class="secondary" @click="form.steps.push({ order: form.steps.length + 1, title: '', description: '', image: '' })">＋ 添加步骤</button>
    </div>

    <div class="actions">
      <button class="secondary" @click="$emit('cancel')">取消</button>
      <button :disabled="saving" @click="save">{{ saving ? '保存中…' : '💾 保存' }}</button>
    </div>
    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api'

const props = defineProps({ recipe: { type: Object, required: true } })
const emit = defineEmits(['saved', 'cancel'])

const form = ref({
  title: props.recipe.title || '',
  author: props.recipe.author || '',
  source_url: props.recipe.source_url || '',
  cooking_time_min: props.recipe.cooking_time_min ?? null,
  servings: props.recipe.servings || '',
  description: props.recipe.description || '',
  ingredients: (props.recipe.ingredients || []).map((i) => ({ ...i })),
  steps: (props.recipe.steps || []).map((s) => ({ ...s })),
})
const tagsText = ref((props.recipe.tags || []).join(', '))
const saving = ref(false)
const error = ref('')

async function save() {
  if (!form.value.title.trim()) {
    error.value = '标题不能为空'
    return
  }
  saving.value = true
  error.value = ''
  try {
    const payload = {
      ...form.value,
      tags: tagsText.value.split(/[,，]/).map((t) => t.trim()).filter(Boolean),
      cooking_time_min: form.value.cooking_time_min || null,
      ingredients: form.value.ingredients.filter((i) => i.name.trim()),
      steps: form.value.steps
        .map((s, i) => ({ ...s, order: i + 1 }))
        .filter((s) => s.description.trim() || s.title.trim()),
    }
    await api.updateRecipe(props.recipe.id, payload)
    emit('saved')
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
h2 { font-size: 18px; margin-bottom: 16px; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 13px; color: #888; margin-bottom: 4px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
.row { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
.step-row { flex-wrap: wrap; }
.step-no {
  width: 24px; height: 24px; border-radius: 50%; background: #e5533c; color: #fff;
  display: inline-flex; align-items: center; justify-content: center; font-size: 13px; flex: none;
}
.col-name { flex: 1.2; }
.col-amount { flex: 1; }
.col-note { flex: 1.6; }
.actions { display: flex; gap: 8px; margin-top: 8px; }
.error { margin-top: 10px; }

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .grid2 { grid-template-columns: 1fr; }
  .row { flex-wrap: wrap; }
  .col-name, .col-amount, .col-note { flex: 1 1 100%; }
  .step-row .col-name, .step-row .col-note { flex: 1 1 100%; }
}
</style>
