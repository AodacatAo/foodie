<template>
  <div class="card">
    <h2>{{ isEdit ? '✏️ 编辑餐厅' : '＋ 录入餐厅' }}</h2>

    <div class="field"><label>店名 *</label><input v-model="form.name" /></div>
    <div class="grid2">
      <div class="field"><label>菜系</label><input v-model="form.cuisine" placeholder="如：川菜" /></div>
      <div class="field"><label>人均（元）</label><input v-model.number="form.price_per_person" type="number" min="0" /></div>
      <div class="field"><label>平台评分（0-5）</label><input v-model.number="form.rating" type="number" min="0" max="5" step="0.1" /></div>
      <div class="field"><label>来源链接</label><input v-model="form.source_url" placeholder="大众点评/美团链接" /></div>
      <div class="field"><label>纬度（可选，用于距离）</label><input v-model.number="form.lat" type="number" step="0.000001" /></div>
      <div class="field"><label>经度（可选，用于距离）</label><input v-model.number="form.lng" type="number" step="0.000001" /></div>
    </div>
    <div class="sync-row">
      <span class="muted">贴大众点评链接后可一键抓取店铺信息 + 封面</span>
      <button class="secondary" :disabled="syncing || !form.source_url" @click="syncDianping">
        {{ syncing ? '抓取中…' : '🔄 从点评抓取' }}
      </button>
    </div>
    <div class="field"><label>地址</label><input v-model="form.address" /></div>
    <div class="field">
      <label>封面图片链接（可选，留空自动生成封面）</label>
      <input v-model="form.cover_image" placeholder="https://… 图片 URL（点评/美团等）" />
    </div>
    <div class="field"><label>标签（逗号分隔）</label><input v-model="tagsText" placeholder="如：宵夜, 聚餐" /></div>

    <div class="field">
      <label>推荐菜（最多 3 个，带图片）</label>
      <div v-for="(dish, i) in form.recommended_dishes" :key="i" class="dish-row">
        <input v-model="dish.name" placeholder="菜名，如：金牌烤鸭" class="dish-name" />
        <label class="dish-upload">
          {{ dish.image ? '换图' : '＋ 图' }}
          <input type="file" accept="image/*" hidden @change="uploadDishImage(dish, $event)" />
        </label>
        <img v-if="dish.image" :src="dish.preview || mediaUrl(dish.image)" class="dish-thumb" alt="" />
        <button class="ghost" @click="form.recommended_dishes.splice(i, 1)">✕</button>
      </div>
      <button
        v-if="form.recommended_dishes.length < 3"
        class="secondary"
        @click="form.recommended_dishes.push({ name: '', image: null, preview: null })"
      >＋ 添加推荐菜</button>
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
import { api, mediaUrl } from '../api'

const props = defineProps({
  restaurant: { type: Object, default: null },
})
const emit = defineEmits(['saved', 'cancel'])

const isEdit = !!props.restaurant
const form = ref({
  name: props.restaurant?.name || '',
  cuisine: props.restaurant?.cuisine || '',
  price_per_person: props.restaurant?.price_per_person ?? null,
  rating: props.restaurant?.rating ?? null,
  source_url: props.restaurant?.source_url || '',
  lat: props.restaurant?.lat ?? null,
  lng: props.restaurant?.lng ?? null,
  address: props.restaurant?.address || '',
  cover_image: props.restaurant?.cover_image?.startsWith('http') ? props.restaurant.cover_image : '',
  recommended_dishes: (props.restaurant?.recommended_dishes || []).map((d) => ({ ...d, preview: null })),
})
const tagsText = ref((props.restaurant?.tags || []).join(', '))
const saving = ref(false)
const syncing = ref(false)
const error = ref('')

async function syncDianping() {
  if (!form.value.source_url.trim()) { error.value = '请先粘贴大众点评链接'; return }
  syncing.value = true
  error.value = ''
  try {
    const info = await api.syncDianping(form.value.source_url.trim())
    form.value.name = info.name || form.value.name
    form.value.cuisine = info.cuisine || form.value.cuisine
    form.value.price_per_person = info.price_per_person ?? form.value.price_per_person
    form.value.rating = info.rating ?? form.value.rating
    form.value.address = info.address || form.value.address
    form.value.cover_image = info.cover_image || form.value.cover_image
    form.value.source_url = info.source_url || form.value.source_url
  } catch (e) { error.value = e.message } finally { syncing.value = false }
}

async function uploadDishImage(dish, e) {
  const f = e.target.files && e.target.files[0]
  e.target.value = ''
  if (!f) return
  try {
    const res = await api.uploadImage(f)
    dish.image = res.path
    dish.preview = URL.createObjectURL(f)
  } catch (err) { error.value = err.message }
}

async function save() {
  if (!form.value.name.trim()) { error.value = '店名不能为空'; return }
  saving.value = true
  error.value = ''
  const payload = {
    ...form.value,
    tags: tagsText.value.split(/[,，]/).map((t) => t.trim()).filter(Boolean),
    price_per_person: form.value.price_per_person || null,
    rating: form.value.rating || null,
    lat: form.value.lat ?? null,
    lng: form.value.lng ?? null,
    recommended_dishes: form.value.recommended_dishes
      .filter((d) => d.name.trim())
      .map((d) => ({ name: d.name.trim(), image: d.image || null })),
  }
  try {
    if (isEdit) await api.updateRestaurant(props.restaurant.id, payload)
    else await api.createRestaurant(payload)
    emit('saved')
  } catch (e) { error.value = e.message } finally { saving.value = false }
}
</script>

<style scoped>
h2 { font-size: 18px; margin-bottom: 16px; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 13px; color: #888; margin-bottom: 4px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
.sync-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.dish-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.dish-name { flex: 1; }
.dish-upload {
  background: #f0ece6; color: #555; border-radius: 8px; padding: 6px 12px;
  font-size: 13px; cursor: pointer; white-space: nowrap;
}
.dish-thumb { width: 44px; height: 44px; border-radius: 6px; object-fit: cover; }
.actions { display: flex; gap: 8px; margin-top: 8px; }
.error { margin-top: 10px; }

/* ---- 移动端 ---- */
@media (max-width: 768px) {
  .grid2 { grid-template-columns: 1fr; }
  .dish-row { flex-wrap: wrap; }
}
</style>
