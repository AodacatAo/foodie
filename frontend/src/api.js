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
  makeShareCard: (id) => req(`/recipes/${id}/share-card`, { method: 'POST' }),
  menuPdfUrl: (origin) => `/api/recipes/menu.pdf?origin=${encodeURIComponent(origin || '')}`,
  listTags: () => req('/recipes/tags'),
  submitManual: (data) => req('/imports/manual', { method: 'POST', body: JSON.stringify(data) }),
  submitXhs: (url) => req('/imports', { method: 'POST', body: JSON.stringify({ url }) }),
  getTask: (id) => req(`/imports/${id}`),
  netInfo: () => req('/net'),
  createOrder: (data) => req('/orders', { method: 'POST', body: JSON.stringify(data) }),
  listOrders: (params = {}) => req(`/orders?${new URLSearchParams(params)}`),
  getOrder: (id) => req(`/orders/${id}`),
  setOrderStatus: (id, status) => req(`/orders/${id}/status`, { method: 'POST', body: JSON.stringify({ status }) }),
  deleteOrder: (id) => req(`/orders/${id}`, { method: 'DELETE' }),
}

export function mediaUrl(path) {
  // /media 带 immutable 长缓存头；内容可变的图片（封面/推荐菜）文件名含时间戳，
  // 更新即新路径新 URL，浏览器自动拉新，无需手工 ?v= 版本号
  return path ? `/media/${path}` : null
}
