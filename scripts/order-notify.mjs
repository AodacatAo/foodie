#!/usr/bin/env node
/**
 * 食集下单微信通知：轮询 NAS 订单 API，发现新订单时通过微信 iLink 主动推送给用户。
 *
 * 依赖：本机已有微信登录态（~/.openclaw/openclaw-weixin/accounts/*.json，@ccchase/dsh-plugin-wechat 登录产物）。
 * 部署：launchd 每 60 秒运行一次（com.foodie.order-notify）。
 *
 * 环境变量（可选）：
 *   FOODIE_API   NAS 食集 API 地址（默认从 ~/.ssh/config 的 nas-git 解析）
 */
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const HOME = os.homedir()
const ACCOUNTS_DIR = path.join(HOME, '.openclaw/openclaw-weixin/accounts')
const STATE_FILE = path.join(HOME, '.openclaw/openclaw-weixin/notified-orders.json')
const PLUGIN_VENDOR = path.join(HOME, '.dsh/profiles/web/node_modules/@ccchase/dsh-plugin-wechat/vendor/weixin/dist/src')

function resolveApiBase() {
  if (process.env.FOODIE_API) return process.env.FOODIE_API.replace(/\/+$/, '')
  // 从 ~/.ssh/config 的 nas-git 条目解析 NAS IP
  try {
    const conf = fs.readFileSync(path.join(HOME, '.ssh/config'), 'utf8')
    const lines = conf.split('\n')
    let active = false
    for (const raw of lines) {
      const line = raw.trim()
      if (/^host\s+/i.test(line)) {
        active = /\bnas-git\b/.test(line)
        continue
      }
      if (active && /^hostname\s+/i.test(line)) {
        return `http://${line.split(/\s+/)[1]}:8080`
      }
    }
  } catch { /* ignore */ }
  return 'http://127.0.0.1:8080'
}

function loadAccount() {
  const files = fs.readdirSync(ACCOUNTS_DIR).filter(
    (f) => f.endsWith('.json') && !f.includes('.context-tokens') && !f.includes('.sync')
  )
  if (!files.length) throw new Error('没有已登录的微信账号')
  const data = JSON.parse(fs.readFileSync(path.join(ACCOUNTS_DIR, files[0]), 'utf8'))
  return {
    accountId: data.accountId || data.account_id,
    token: data.token || data.botToken,
    baseUrl: data.baseUrl || 'https://ilinkai.weixin.qq.com',
    userId: data.userId || data.user_id,
  }
}

function loadNotified() {
  try {
    return new Set(JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')))
  } catch {
    return new Set()
  }
}

function saveNotified(set) {
  fs.writeFileSync(STATE_FILE, JSON.stringify([...set]))
}

async function main() {
  const base = resolveApiBase()
  const account = loadAccount()
  if (!account.token || !account.userId) throw new Error('账号凭据不完整（token/userId）')

  // 拉取最近订单
  const res = await fetch(`${base}/api/orders?page_size=10`)
  if (!res.ok) throw new Error(`订单 API ${res.status}`)
  const { items } = await res.json()

  const notified = loadNotified()
  const fresh = items.filter((o) => !notified.has(String(o.id)))

  // 首次运行：只记录不打扰
  if (fresh.length === items.length && fresh.length > 0 && notified.size === 0) {
    for (const o of items) notified.add(String(o.id))
    saveNotified(notified)
    console.log(`[首次运行] 已跳过历史 ${items.length} 条订单，之后新订单会通知微信`)
    return
  }

  for (const o of fresh) {
    const detail = (o.items || []).map((i) => `${i.title}×${i.qty}`).join('、')
    const text = `📋 新订单：${o.person || '家人'} 点了 ${o.items.length} 道菜 · 合计 ¥${o.total}\n${detail}`
    const { sendMessageWeixin } = await import(`file://${path.join(PLUGIN_VENDOR, 'messaging/send.js')}`)
    await sendMessageWeixin({
      to: account.userId,
      text,
      opts: { baseUrl: account.baseUrl, token: account.token },
    })
    notified.add(String(o.id))
    console.log(`已通知微信：订单#${o.id}（${o.person || '家人'} ¥${o.total}）`)
  }
  if (fresh.length) saveNotified(notified)
}

main().catch((e) => {
  console.error(new Date().toISOString(), '通知失败:', e.message)
  process.exitCode = 1
})
