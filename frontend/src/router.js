import { createRouter, createWebHashHistory } from 'vue-router'

// 路由懒加载：每个页面独立分包，首屏只加载当前页面
const RecipeList = () => import('./views/RecipeList.vue')
const MenuView = () => import('./views/MenuView.vue')
const OrderView = () => import('./views/OrderView.vue')
const RecipeDetail = () => import('./views/RecipeDetail.vue')
const ImportView = () => import('./views/ImportView.vue')
const RestaurantList = () => import('./views/RestaurantList.vue')
const RestaurantDetail = () => import('./views/RestaurantDetail.vue')
const RestaurantNew = () => import('./views/RestaurantNew.vue')
const SettingsView = () => import('./views/SettingsView.vue')

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'list', component: RecipeList },
    { path: '/menu', name: 'menu', component: MenuView },
    { path: '/order', name: 'order', component: OrderView, meta: { hideNav: true } },
    { path: '/recipe/:id', name: 'detail', component: RecipeDetail },
    { path: '/import', name: 'import', component: ImportView },
    { path: '/restaurants', name: 'restaurants', component: RestaurantList },
    { path: '/restaurant/new', name: 'restaurant-new', component: RestaurantNew },
    { path: '/restaurant/:id', name: 'restaurant-detail', component: RestaurantDetail },
    { path: '/settings', name: 'settings', component: SettingsView },
  ],
})
