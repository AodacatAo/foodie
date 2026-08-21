<template>
  <div class="app">
    <header v-if="!$route.meta.hideNav" class="topbar">
      <router-link to="/" class="brand">
        <span class="brand-mark"><Icon name="bowl" :size="20" /></span>
        <span class="brand-text">食集</span>
      </router-link>
      <nav class="desktop-nav">
        <router-link
          v-for="n in navs" :key="n.key"
          :to="n.target"
          class="nav-item"
          :class="{ on: isActive(n) }"
        >
          <Icon :name="n.icon" :size="16" />
          <span>{{ n.label }}</span>
        </router-link>
      </nav>
    </header>
    <main class="container">
      <router-view />
    </main>

    <!-- 移动端底部悬浮导航（与桌面同一套 active 逻辑） -->
    <nav v-if="!$route.meta.hideNav" class="mobile-tabbar">
      <router-link
        v-for="n in navs" :key="n.key"
        :to="n.target"
        class="tab-item"
        :class="{ on: isActive(n) }"
      >
        <span class="tab-pill"><Icon :name="n.icon" :size="20" /></span>
        <span class="tab-label">{{ n.label }}</span>
      </router-link>
    </nav>

    <!-- 访问密码登录 -->
    <div v-if="showLogin" class="login-overlay">
      <div class="login-card">
        <div class="login-logo"><Icon name="bowl" :size="40" /></div>
        <h1>食集</h1>
        <p class="muted">私人美食库，请输入访问密码</p>
        <input
          v-model="token" type="password" placeholder="访问密码"
          autocomplete="current-password" @keyup.enter="doLogin"
        />
        <button :disabled="loggingIn" @click="doLogin">{{ loggingIn ? '验证中…' : '🔓 进入' }}</button>
        <p v-if="loginError" class="login-error">{{ loginError }}</p>
      </div>
    </div>
  </div>
</template>

<script>
import Icon from './components/Icon.vue'

export default {
  components: { Icon },
  data: () => ({ showLogin: false, token: '', loginError: '', loggingIn: false }),
  computed: {
    // 统一激活判定：菜谱 / 草稿 同属 list 路由但按 query 区分，绝不双高亮
    navs() {
      return [
        { key: 'list', label: '菜谱库', icon: 'bowl', target: { name: 'list' }, match: () => ['list', 'detail'].includes(this.$route.name) && this.$route.query.status !== 'draft' },
        { key: 'menu', label: '菜单', icon: 'menu', target: { name: 'menu' }, match: () => this.$route.name === 'menu' },
        { key: 'import', label: '导入', icon: 'import', target: { name: 'import' }, match: () => this.$route.name === 'import' },
        { key: 'draft', label: '草稿箱', icon: 'draft', target: { name: 'list', query: { status: 'draft' } }, match: () => this.$route.name === 'list' && this.$route.query.status === 'draft' },
        { key: 'settings', label: '设置', icon: 'settings', target: { name: 'settings' }, match: () => this.$route.name === 'settings' },
      ]
    },
  },
  methods: {
    isActive(n) { return n.match() },
    mounted() {
      window.addEventListener('foodie:unauthorized', this.openLogin)
    },
    beforeUnmount() {
      window.removeEventListener('foodie:unauthorized', this.openLogin)
    },
    openLogin() { this.showLogin = true },
    async doLogin() {
      if (!this.token) { this.loginError = '请输入密码'; return }
      this.loggingIn = true
      this.loginError = ''
      try {
        const res = await fetch('/api/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: this.token }),
        })
        if (!res.ok) { this.loginError = '密码不对，再试一次'; return }
        location.reload()  // 带 Cookie 重新加载
      } catch {
        this.loginError = '网络错误，请重试'
      } finally {
        this.loggingIn = false
      }
    },
  },
}
</script>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 28px;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(16px) saturate(1.4);
  -webkit-backdrop-filter: blur(16px) saturate(1.4);
  border-bottom: 1px solid rgba(240, 235, 228, 0.9);
  position: sticky;
  top: 0;
  z-index: 40;
}
.brand { display: flex; align-items: center; gap: 9px; text-decoration: none; }
.brand-mark {
  display: inline-flex; align-items: center; justify-content: center;
  width: 34px; height: 34px; border-radius: 11px;
  background: var(--brand-grad); color: #fff;
  box-shadow: 0 3px 10px rgba(229, 83, 60, 0.32);
}
.brand-text {
  font-size: 21px; font-weight: 800; letter-spacing: 1px;
  background: linear-gradient(135deg, #f06a4f, #e5533c);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}
nav { display: flex; gap: 4px; }
.nav-item {
  display: inline-flex; align-items: center; gap: 6px;
  color: #7a6a58; text-decoration: none;
  font-size: 14px; font-weight: 600;
  padding: 8px 14px; border-radius: 12px;
  transition: background 0.15s, color 0.15s;
}
.nav-item:hover { background: #f6efe8; color: #5c4f41; }
.nav-item.on {
  color: var(--brand-deep);
  background: var(--brand-soft);
  box-shadow: inset 0 0 0 1px rgba(229, 83, 60, 0.14);
}
.container { max-width: 1200px; margin: 0 auto; padding: 26px 20px 64px; }

/* 移动端底部悬浮导航 */
.mobile-tabbar { display: none; }

/* 登录遮罩 */
.login-overlay {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(250, 248, 245, 0.97);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.login-card {
  width: 100%; max-width: 320px;
  background: #fff; border-radius: 16px;
  padding: 32px 24px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1);
  text-align: center;
  display: flex; flex-direction: column; gap: 12px;
}
.login-logo {
  margin: 0 auto; width: 64px; height: 64px; border-radius: 20px;
  background: var(--brand-grad); color: #fff;
  display: flex; align-items: center; justify-content: center;
}
.login-card h1 { font-size: 24px; color: #e5533c; }
.login-card input { text-align: center; }
.login-card button { padding: 12px; font-size: 15px; }
.login-error { color: #d33; font-size: 13px; }

@media (max-width: 768px) {
  .desktop-nav { display: none; }
  .topbar { padding: 10px 16px; }
  .brand-text { font-size: 19px; }
  .container { padding: 14px 12px 96px; }
  .mobile-tabbar {
    display: flex;
    position: fixed;
    left: 12px; right: 12px; bottom: calc(10px + env(safe-area-inset-bottom));
    z-index: 60;
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(16px) saturate(1.4);
    -webkit-backdrop-filter: blur(16px) saturate(1.4);
    border-radius: 22px;
    border: 1px solid rgba(240, 235, 228, 0.9);
    box-shadow: 0 8px 28px rgba(93, 63, 41, 0.14);
    padding: 7px 6px;
  }
  .tab-item {
    flex: 1;
    display: flex; flex-direction: column; align-items: center; gap: 3px;
    text-decoration: none; color: #9a8a76;
  }
  .tab-pill {
    display: flex; align-items: center; justify-content: center;
    width: 40px; height: 30px; border-radius: 12px;
    transition: background 0.18s, color 0.18s;
  }
  .tab-item.on { color: var(--brand-deep); font-weight: 700; }
  .tab-item.on .tab-pill { background: var(--brand-grad); color: #fff; box-shadow: 0 3px 8px rgba(229, 83, 60, 0.35); }
  .tab-label { font-size: 10.5px; }
}
</style>
