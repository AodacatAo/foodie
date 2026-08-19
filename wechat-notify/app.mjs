#!/usr/bin/env node
/**
 * 微信即时通知独立服务（与食集解耦）
 *
 * POST /notify  {"text": "..."}   → 向用户微信推送（iLink 官方协议，秒级）
 * GET  /healthz                   → 健康检查
 *
 * 凭据：/data/account.json（{token, userId, baseUrl}，登录产物迁移）
 * 可选鉴权：环境变量 NOTIFY_TOKEN 非空时，请求需 Authorization: Bearer <token>
 */
import http from 'node:http'
import crypto from 'node:crypto'
import fs from 'node:fs'

const PORT = Number(process.env.PORT || 8090)
const NOTIFY_TOKEN = process.env.NOTIFY_TOKEN || ''
const ACCOUNT_FILE = process.env.ACCOUNT_FILE || '/data/account.json'

const ILINK_APP_ID = 'bot'
const ILINK_APP_CLIENT_VERSION = (2 << 16) | (4 << 8) | 6 // 2.4.6
const CHANNEL_VERSION = '2.4.6'
const BOT_AGENT = 'OpenClaw'

function loadAccount() {
  try {
    const d = JSON.parse(fs.readFileSync(ACCOUNT_FILE, 'utf8'))
    if (d.token && d.userId) return d
  } catch {}
  return null
}

function wechatUin() {
  const u32 = crypto.randomBytes(4).readUInt32BE(0)
  return Buffer.from(String(u32), 'utf8').toString('base64')
}

async function sendWechat(text) {
  const account = loadAccount()
  if (!account) throw new Error('账号凭据缺失（/data/account.json）')
  const base = account.baseUrl || 'https://ilinkai.weixin.qq.com'
  const body = {
    msg: {
      from_user_id: '',
      to_user_id: account.userId,
      client_id: `wechat-notify:${Date.now()}-${crypto.randomBytes(4).toString('hex')}`,
      message_type: 2, // BOT
      message_state: 2, // FINISH
      item_list: [{ type: 1, text_item: { text } }], // TEXT
    },
    base_info: { channel_version: CHANNEL_VERSION, bot_agent: BOT_AGENT },
  }
  const res = await fetch(`${base}/ilink/bot/sendmessage`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      AuthorizationType: 'ilink_bot_token',
      Authorization: `Bearer ${account.token}`,
      'X-WECHAT-UIN': wechatUin(),
      'iLink-App-Id': ILINK_APP_ID,
      'iLink-App-ClientVersion': String(ILINK_APP_CLIENT_VERSION),
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  })
  if (!res.ok) throw new Error(`iLink HTTP ${res.status}: ${await res.text()}`)
  const resp = await res.json()
  if (resp.ret && resp.ret !== 0) throw new Error(`iLink ret=${resp.ret} errmsg=${resp.errmsg ?? ''}`)
}

function json(res, code, obj) {
  res.writeHead(code, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify(obj))
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/healthz') {
    return json(res, 200, { ok: true, ready: !!loadAccount() })
  }
  if (req.method === 'POST' && req.url === '/notify') {
    if (NOTIFY_TOKEN && req.headers.authorization !== `Bearer ${NOTIFY_TOKEN}`) {
      return json(res, 401, { ok: false, error: 'unauthorized' })
    }
    let body = ''
    for await (const chunk of req) body += chunk
    let text = ''
    try { text = String(JSON.parse(body).text || '').trim().slice(0, 500) } catch { /* bad json */ }
    if (!text) return json(res, 400, { ok: false, error: 'text required' })
    try {
      await sendWechat(text)
      console.log(new Date().toISOString(), 'sent:', text.slice(0, 50))
      return json(res, 200, { ok: true, sent: true })
    } catch (e) {
      console.error(new Date().toISOString(), 'send failed:', e.message)
      return json(res, 503, { ok: false, sent: false, error: e.message })
    }
  }
  json(res, 404, { ok: false, error: 'not found' })
})

server.listen(PORT, '0.0.0.0', () => {
  console.log(`wechat-notify listening on :${PORT}${NOTIFY_TOKEN ? ' (token required)' : ''}`)
})
