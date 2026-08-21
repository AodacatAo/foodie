<template>
  <div class="settings-page">
    <!-- 顶部横幅 -->
    <div class="strip">
      <div>
        <h1 class="strip-title">设置</h1>
        <p class="strip-sub">局域网访问 · 关于食集</p>
      </div>
      <div class="strip-icon"><Icon name="settings" :size="22" /></div>
    </div>

    <div class="content">
      <!-- 局域网访问 -->
      <div class="card set-card">
        <h2 class="card-title"><Icon name="wifi" :size="16" /> 局域网访问</h2>
        <p class="muted desc">
          手机 / 平板连同一个 Wi-Fi 打开下面地址即可，<b>免登录</b>（外网访问才需要密码，登录一次管一年）。
        </p>
        <div v-if="net.ips.length" class="lan-ips">
          <div v-for="(ip, i) in net.ips" :key="ip" class="lan-row">
            <code>http://{{ ip }}:{{ net.port }}</code>
            <button class="copy-btn" :class="{ done: copiedKey === 'ip' + i }" @click="copyIp(ip, net.port, 'ip' + i)">
              <Icon v-if="copiedKey !== 'ip' + i" name="check" :size="13" />
              {{ copiedKey === 'ip' + i ? '已复制 ✓' : '复制' }}
            </button>
          </div>
        </div>
        <p v-else class="muted">正在获取局域网地址…</p>
        <p class="muted current">当前打开地址：<code>{{ locationHost }}</code></p>
      </div>

      <!-- 关于 -->
      <div class="card set-card about-card">
        <h2 class="card-title"><Icon name="bowl" :size="16" /> 关于食集</h2>
        <div class="about-row">
          <div class="about-logo"><Icon name="bowl" :size="26" /></div>
          <div class="about-meta">
            <b>食集 · 综合美食 Web</b>
            <p class="muted">菜谱 + 菜单点餐，数据全部存在 NAS（每日异池备份）</p>
          </div>
        </div>
        <div class="about-chips">
          <span class="chip">Vue3 + Vite</span>
          <span class="chip">FastAPI + SQLite</span>
          <span class="chip">NAS Docker 常驻</span>
          <a class="chip link" href="https://github.com/AodacatAo/foodie" target="_blank" rel="noopener">GitHub ↗</a>
        </div>
        <p class="muted backup-note">
          备份：<code>scripts/nas_backup.sh</code> 每日 04:15 异池快照，保留 14 天
        </p>
      </div>
    </div>
  </div>
</template>


<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import Icon from '../components/Icon.vue'

const error = ref('')
const net = ref({ ips: [], port: 8080 })
const locationHost = ref(window.location.host)
const copiedKey = ref('')

async function loadNet() {
  try {
    const data = await api.netInfo()
    net.value = data
  } catch { /* 忽略 */ }
}

async function copyIp(ip, port, key) {
  try {
    await navigator.clipboard.writeText(`http://${ip}:${port}`)
    copiedKey.value = key
    setTimeout(() => { copiedKey.value = '' }, 1600)
  } catch {
    error.value = '复制失败，请手动输入'
  }
}

onMounted(loadNet)
</script>

<style scoped>
.settings-page {
  background:
    radial-gradient(900px 500px at 85% -80px, rgba(240, 106, 79, 0.14), transparent 60%),
    radial-gradient(700px 400px at -15% 30%, rgba(245, 166, 35, 0.10), transparent 60%),
    var(--bg);
  min-height: 100vh;
  margin: -26px -20px -64px;
  padding: 26px 20px 70px;
}
.strip {
  display: flex; align-items: center; justify-content: space-between;
  background: linear-gradient(120deg, #fdeeea, #fdf3dc);
  border: 1px solid rgba(240, 229, 216, 0.9);
  border-radius: 20px;
  padding: 14px 20px;
  margin-bottom: 14px;
}
.strip-title { font-size: 20px; font-weight: 800; color: #2f2a24; }
.strip-sub { font-size: 12.5px; color: #a08d7a; margin-top: 3px; }
.strip-icon {
  width: 44px; height: 44px; border-radius: 14px; flex: none;
  background: var(--brand-grad); color: #fff;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 16px rgba(229, 83, 60, 0.3);
}
.content { display: flex; flex-direction: column; gap: 14px; }
.set-card { animation: rise 0.45s ease both; }
.set-card:nth-child(2) { animation-delay: 0.08s; }
@keyframes rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
.card-title { display: flex; align-items: center; gap: 6px; font-size: 17px; font-weight: 800; color: #2f2a24; margin-bottom: 8px; }
.card-title :deep(.icon) { color: var(--brand); }
.desc { line-height: 1.7; margin-bottom: 12px; }

.lan-ips { display: flex; flex-direction: column; gap: 8px; margin: 10px 0; }
.lan-row { display: flex; align-items: center; gap: 10px; }
.lan-row code {
  flex: 1; background: #f5f1ea;
  padding: 9px 12px; border-radius: 12px; font-size: 14px;
  color: #5c4f41; font-weight: 600;
  border: 1px solid rgba(240, 235, 228, 0.9);
}
.copy-btn {
  flex: none; display: inline-flex; align-items: center; gap: 4px;
  background: var(--brand-soft); color: var(--brand-deep);
  padding: 8px 14px; font-size: 13px; font-weight: 700;
}
.copy-btn.done { background: #e8f5e9; color: #2e7d32; }
.current { margin-top: 4px; }
.current code { background: #f3ede5; border-radius: 6px; padding: 1px 6px; font-size: 12px; }

.about-row { display: flex; align-items: center; gap: 12px; margin: 4px 0 12px; }
.about-logo {
  width: 52px; height: 52px; border-radius: 16px; flex: none;
  background: var(--brand-grad); color: #fff;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 16px rgba(229, 83, 60, 0.3);
}
.about-meta b { font-size: 15px; color: #2f2a24; }
.about-meta p { margin-top: 2px; }
.about-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12px; font-weight: 600; color: #7a6a58;
  background: #f7f3ec; border-radius: 12px; padding: 3px 10px;
}
.chip.link { color: var(--brand-deep); background: var(--brand-soft); text-decoration: none; }
.backup-note code { background: #f3ede5; border-radius: 6px; padding: 1px 6px; font-size: 12px; }

@media (max-width: 768px) {
  .settings-page { margin: -14px -12px -96px; padding: 14px 12px 100px; }
  .strip { padding: 12px 14px; border-radius: 16px; }
  .strip-title { font-size: 18px; }
}
</style>
