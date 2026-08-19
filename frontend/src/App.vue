<template>
  <div class="app">
    <header v-if="!$route.meta.hideNav" class="topbar">
      <router-link to="/" class="brand">🍜 食集</router-link>
      <nav class="desktop-nav">
        <router-link to="/">菜谱库</router-link>
        <router-link to="/menu">菜单</router-link>
        <router-link to="/restaurants">餐厅库</router-link>
        <router-link to="/import">导入</router-link>
        <router-link :to="{ path: '/', query: { status: 'draft' } }">草稿箱</router-link>
        <router-link to="/settings">设置</router-link>
      </nav>
    </header>
    <main class="container">
      <router-view />
    </main>

    <!-- 移动端底部导航 -->
    <nav v-if="!$route.meta.hideNav" class="mobile-tabbar">
      <router-link
        to="/"
        :class="{ active: $route.path === '/' && $route.query.status !== 'draft' }"
      ><span class="tab-icon">🍜</span><span>菜谱</span></router-link>
      <router-link
        to="/menu"
        :class="{ active: $route.path === '/menu' }"
      ><span class="tab-icon">📋</span><span>菜单</span></router-link>
      <router-link
        to="/restaurants"
        :class="{ active: $route.path.startsWith('/restaurant') }"
      ><span class="tab-icon">🍽</span><span>餐厅</span></router-link>
      <router-link
        to="/import"
        :class="{ active: $route.path === '/import' }"
      ><span class="tab-icon">📥</span><span>导入</span></router-link>
      <router-link
        :to="{ path: '/', query: { status: 'draft' } }"
        :class="{ active: $route.path === '/' && $route.query.status === 'draft' }"
      ><span class="tab-icon">📝</span><span>草稿</span></router-link>
      <router-link
        to="/settings"
        :class="{ active: $route.path === '/settings' }"
      ><span class="tab-icon">⚙️</span><span>设置</span></router-link>
    </nav>

    <!-- 访问密码登录 -->
    <div v-if="showLogin" class="login-overlay">
      <div class="login-card">
        <div class="login-logo">🍜</div>
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
export default {
  data: () => ({ showLogin: false, token: '', loginError: '', loggingIn: false }),
  mounted() {
    window.addEventListener('foodie:unauthorized', this.openLogin)
  },
  beforeUnmount() {
    window.removeEventListener('foodie:unauthorized', this.openLogin)
  },
  methods: {
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
  padding: 14px 24px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(240, 235, 228, 0.8);
  position: sticky;
  top: 0;
  z-index: 10;
}
.brand {
  font-size: 21px;
  font-weight: 800;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, #f06a4f, #e5533c);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  text-decoration: none;
}
nav { display: flex; gap: 6px; }
nav a {
  color: #7a6a58;
  text-decoration: none;
  font-size: 14.5px;
  font-weight: 500;
  padding: 7px 14px;
  border-radius: 20px;
  transition: background 0.15s, color 0.15s;
}
nav a:hover { background: #f6efe8; color: #5c4f41; }
nav a.router-link-active { color: #fff; background: var(--brand-grad); font-weight: 600; box-shadow: 0 2px 8px rgba(229, 83, 60, 0.28); }
.container { max-width: 1080px; margin: 0 auto; padding: 26px 16px 60px; }

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
.login-logo { font-size: 44px; }
.login-card h1 { font-size: 24px; color: #e5533c; }
.login-card input { text-align: center; }
.login-card button { padding: 12px; font-size: 15px; }
.login-error { color: #d33; font-size: 13px; }

@media (max-width: 768px) {
  .desktop-nav { display: none; }
  .topbar { padding: 10px 16px; }
  .container { padding: 14px 12px 90px; }
  .mobile-tabbar {
    display: flex;
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: #fff;
    border-top: 1px solid #eee;
    z-index: 60;
    padding-bottom: env(safe-area-inset-bottom);
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.04);
  }
  .mobile-tabbar a {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    padding: 7px 0 6px;
    font-size: 11px;
    color: #888;
    text-decoration: none;
  }
  .mobile-tabbar a .tab-icon { font-size: 20px; line-height: 1.1; }
  .mobile-tabbar a.active { color: #e5533c; font-weight: 600; }
}
</style>
