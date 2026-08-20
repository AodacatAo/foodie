const BASE = '/api'

function onUnauthorized() {
  window.dispatchEvent(new CustomEvent('foodie:unauthorized'))
}

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (res.status === 401) {
    onUnauthorized()
    throw new Error('需要登录')
  }
  if (!res.ok) {
    let msg = res.statusText
    try {
      const body = await res.json()
      if (Array.isArray(body.detail)) msg = body.detail.map((d) => d.msg).join('; ')
      else if (body.detail) msg = body.detail
    } catch { /* ignore */ }
    throw new Error(msg || '请求失败')
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  listRecipes: (params = {}) => req(`/recipes?${new URLSearchParams(params)}`),
  getRecipe: (id) => req(`/recipes/${id}`),
  createRecipe: (data) => req('/recipes', { method: 'POST', body: JSON.stringify(data) }),
  updateRecipe: (id, data) => req(`/recipes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  publishRecipe: (id) => req(`/recipes/${id}/publish`, { method: 'POST' }),
  deleteRecipe: (id) => req(`/recipes/${id}`, { method: 'DELETE' }),
  putOnMenu: (id) => req(`/recipes/${id}/menu`, { method: 'POST' }),
  takeOffMenu: (id) => req(`/recipes/${id}/menu`, { method: 'DELETE' }),
  toggleWant: (id) => req(`/recipes/${id}/want`, { method: 'POST' }),
  setMenuPrice: (id, price) => req(`/recipes/${id}/menu-price`, { method: 'POST', body: JSON.stringify({ price }) }),
  setMenuCategory: (id, category) => req(`/recipes/${id}/menu-category`, { method: 'POST', body: JSON.stringify({ category }) }),
  listTags: () => req('/recipes/tags'),
  submitManual: (data) => req('/imports/manual', { method: 'POST', body: JSON.stringify(data) }),
  submitXhs: (url) => req('/imports', { method: 'POST', body: JSON.stringify({ url }) }),
  getTask: (id) => req(`/imports/${id}`),
  // ---- 餐厅库 ----
  listRestaurants: (params = {}) => req(`/restaurants?${new URLSearchParams(params)}`),
  getRestaurant: (id) => req(`/restaurants/${id}`),
  createRestaurant: (data) => req('/restaurants', { method: 'POST', body: JSON.stringify(data) }),
  updateRestaurant: (id, data) => req(`/restaurants/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteRestaurant: (id) => req(`/restaurants/${id}`, { method: 'DELETE' }),
  publishRestaurant: (id) => req(`/restaurants/${id}/publish`, { method: 'POST' }),
  syncDishes: (id) => req(`/restaurants/${id}/sync-dishes`, { method: 'POST' }),
  setMyRating: (id, my_rating) => req(`/restaurants/${id}/rating`, { method: 'POST', body: JSON.stringify({ my_rating }) }),
  uploadImage: async (file) => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('/api/restaurants/upload', { method: 'POST', body: form })
    if (res.status === 401) {
      onUnauthorized()
      throw new Error('需要登录')
    }
    if (!res.ok) {
      let msg = res.statusText
      try { msg = (await res.json()).detail || msg } catch { /* ignore */ }
      throw new Error(msg)
    }
    return res.json()
  },
  syncDianping: (url) => req('/restaurants/sync-info', { method: 'POST', body: JSON.stringify({ url }) }),
  searchShops: (keyword) => req('/restaurants/search-shops', { method: 'POST', body: JSON.stringify({ keyword }) }),
  listVisits: (id) => req(`/restaurants/${id}/visits`),
  addVisit: (id, data) => req(`/restaurants/${id}/visits`, { method: 'POST', body: JSON.stringify(data) }),
  updateVisit: (id, data) => req(`/restaurants/visits/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteVisit: (id) => req(`/restaurants/visits/${id}`, { method: 'DELETE' }),
  listLocations: () => req('/locations'),
  createLocation: (data) => req('/locations', { method: 'POST', body: JSON.stringify(data) }),
  deleteLocation: (id) => req(`/locations/${id}`, { method: 'DELETE' }),
  netInfo: () => req('/net'),
  createOrder: (data) => req('/orders', { method: 'POST', body: JSON.stringify(data) }),
  listOrders: (params = {}) => req(`/orders?${new URLSearchParams(params)}`),
  deleteOrder: (id) => req(`/orders/${id}`, { method: 'DELETE' }),
}

export function mediaUrl(path) {
  // ?v=3：缓存版本号。图片内容更新时（如推荐菜换成真图）需要递增此值强制浏览器重新拉取
  return path ? `/media/${path}?v=3` : null
}
