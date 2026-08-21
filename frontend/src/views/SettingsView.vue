<template>
  <div>
    <h1 class="page-title">设置</h1>

    <div class="card">
      <h2>局域网访问</h2>
      <p class="muted">手机 / 平板连同一个 Wi-Fi 打开下面地址即可，<b>免登录</b>（外网访问才需要密码，登录一次管一年）。</p>
      <div v-if="net.ips.length" class="lan-ips">
        <div v-for="ip in net.ips" :key="ip" class="lan-row">
          <code>http://{{ ip }}:{{ net.port }}</code>
          <button class="secondary small" @click="copyIp(ip, net.port)">复制</button>
        </div>
      </div>
      <p v-else class="muted">正在获取局域网地址…</p>
      <p class="muted">当前打开地址：<code>{{ locationHost }}</code></p>
    </div>

    <div class="card">
      <h2>关于</h2>
      <p class="muted">食集 · 本地美食库：菜谱 + 菜单点餐，数据全部存在 NAS（/share/ZFS2_DATA/foodie/data/），每日异池备份。</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const error = ref('')
const net = ref({ ips: [], port: 8080 })
const locationHost = ref(window.location.host)

async function loadNet() {
  try {
    const data = await api.netInfo()
    net.value = data
  } catch { /* 忽略 */ }
}

async function copyIp(ip, port) {
  try {
    await navigator.clipboard.writeText(`http://${ip}:${port}`)
    error.value = ''
  } catch {
    error.value = '复制失败，请手动输入'
  }
}

onMounted(loadNet)
</script>

<style scoped>
.page-title { font-size: 22px; margin-bottom: 14px; }
.card { margin-bottom: 14px; }
.card h2 { font-size: 17px; margin-bottom: 8px; color: #e5533c; }
.lan-ips { display: flex; flex-direction: column; gap: 8px; margin: 10px 0; }
.lan-row { display: flex; align-items: center; gap: 10px; }
.lan-row code { background: #f5f1ea; padding: 6px 10px; border-radius: 8px; font-size: 14px; }
button.small { padding: 4px 12px; font-size: 12px; }
</style>
