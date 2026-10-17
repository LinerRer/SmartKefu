<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { SwitchButton, RefreshRight, ChatDotRound, Promotion, Check } from '@element-plus/icons-vue'
import http from '../api'

interface ChatMsg {
  role: 'user' | 'ai'
  content: string
  references: any[]
  suggestHuman: boolean
}

const kbs = ref<any[]>([])
const kbId = ref<number>()
const currentKbName = ref('')
const token = ref('')
const msgs = reactive<ChatMsg[]>([])
const question = ref('')
const sending = ref(false)
const listEl = ref<HTMLElement>()
const showKbPicker = ref(false)
const activeRefs = ref<number[]>([])
const loadError = ref('')
const suggestedQuestions = computed(() => {
  const name = currentKbName.value
  return [
    `${name || '知识库'}主要包含哪些内容？`,
    '请介绍一下核心概念',
    '常见问题有哪些？',
    '如何快速上手？',
  ]
})

onMounted(async () => {
  try {
    const res: any = await http.get('/kb/public')
    kbs.value = res.data
  } catch (e: any) {
    loadError.value = '无法连接服务器，请确认后端已启动后刷新页面'
  }
})

function selectKb(id: number) {
  kbId.value = id
  const kb = kbs.value.find((k) => k.id === id)
  currentKbName.value = kb?.name || ''
  showKbPicker.value = false
}

async function startSession() {
  if (!kbId.value) { ElMessage.warning('请先选择知识库'); return }
  const kb = kbs.value.find((k) => k.id === kbId.value)
  currentKbName.value = kb?.name || ''
  const res: any = await http.post('/chat/conversations', { kb_id: kbId.value })
  token.value = res.data.conversation_token
  msgs.splice(0, msgs.length)
  msgs.push({
    role: 'ai',
    content: `你好！我是基于「${currentKbName.value}」的 AI 客服，有什么可以帮您？`,
    references: [],
    suggestHuman: false,
  })
}

function newSession() {
  // 回到选库界面，清空当前会话
  token.value = ''
  msgs.splice(0, msgs.length)
  humanMode.value = false
  if (vws.value) { vws.value.close(); vws.value = null }
}

function useSuggestion(q: string) {
  question.value = q
  send()
}

async function send() {
  const q = question.value.trim()
  if (!q || sending.value) return
  msgs.push({ role: 'user', content: q, references: [], suggestHuman: false })
  question.value = ''
  scrollToBottom()

  // 人工模式：消息走 WS 直转坐席，不再请求 AI
  if (humanMode.value && vws.value?.readyState === WebSocket.OPEN) {
    vws.value.send(JSON.stringify({ type: 'message', text: q }))
    return
  }

  const aiMsg = reactive<ChatMsg>({ role: 'ai', content: '', references: [], suggestHuman: false })
  msgs.push(aiMsg)
  sending.value = true
  scrollToBottom()

  try {
    const resp = await fetch('/api/v1/chat/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: token.value, question: q }),
    })
    if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)

    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
      let idx: number
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        handleEvent(buf.slice(0, idx), aiMsg)
        buf = buf.slice(idx + 2)
        scrollToBottom()
      }
    }
  } catch (err: any) {
    aiMsg.content = aiMsg.content || '抱歉，本次请求失败了，请重试。'
    ElMessage.error(err.message || '请求失败')
  } finally {
    sending.value = false
  }
}

function handleEvent(raw: string, aiMsg: ChatMsg) {
  let event = 'message'
  let data = ''
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data += line.slice(5).trim()
  }
  if (!data) return
  const payload = JSON.parse(data)
  if (event === 'meta') {
    aiMsg.references = payload.references || []
    aiMsg.suggestHuman = payload.suggest_human
  } else if (event === 'delta') {
    feedText(aiMsg, payload.text)
  }
}

// 打字机平滑
let typeTimer: number | null = null
let typeQueue = ''
let typeTarget: ChatMsg | null = null

function feedText(msg: ChatMsg, text: string) {
  if (typeTarget && typeTarget !== msg) {
    typeTarget.content += typeQueue
    typeQueue = ''
  }
  typeTarget = msg
  typeQueue += text
  if (typeTimer !== null) return
  typeTimer = window.setInterval(() => {
    if (!typeTarget) return
    if (!typeQueue) { window.clearInterval(typeTimer!); typeTimer = null; return }
    typeTarget.content += typeQueue.slice(0, 2)
    typeQueue = typeQueue.slice(2)
    scrollToBottom()
  }, 24)
}

function scrollToBottom() {
  nextTick(() => {
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  })
}

// 转人工
const humanMode = ref(false)
const vws = ref<WebSocket | null>(null)

function toHuman() {
  if (vws.value?.readyState === WebSocket.OPEN) {
    vws.value.send(JSON.stringify({ type: 'human' }))
    return
  }
  if (vws.value?.readyState === WebSocket.CONNECTING) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const sock = new WebSocket(`${proto}://${location.host}/api/v1/ws/visitor/${token.value}`)
  sock.onopen = () => sock.send(JSON.stringify({ type: 'human' }))
  sock.onmessage = (e) => {
    const msg = JSON.parse(e.data)
    if (msg.type === 'human_result') {
      humanMode.value = true
      msgs.push({ role: 'ai', content: msg.accepted
        ? '已为您接入人工客服，请描述您的问题。'
        : '暂无客服在线，已为您排队，您可以先留言，坐席上线后会自动收到。',
        references: [], suggestHuman: false })
    } else if (msg.type === 'agent_message') {
      msgs.push({ role: 'ai', content: `【人工客服】${msg.text}`, references: [], suggestHuman: false })
      scrollToBottom()
    } else if (msg.type === 'human_closed') {
      humanMode.value = false
      msgs.push({ role: 'ai', content: msg.text, references: [], suggestHuman: false })
      scrollToBottom()
    } else if (msg.type === 'system') {
      msgs.push({ role: 'ai', content: msg.text, references: [], suggestHuman: false })
    }
  }
  sock.onclose = () => { humanMode.value = false; vws.value = null }
  vws.value = sock
}

function leaveHuman() {
  if (vws.value?.readyState === WebSocket.OPEN) {
    vws.value.send(JSON.stringify({ type: 'leave_human' }))
  } else {
    humanMode.value = false
  }
}
</script>

<template>
  <div class="chat-wrap">
    <!-- 未开始会话：选知识库 -->
    <div v-if="!token" class="start-screen">
      <div class="start-card">
        <div class="start-icon">
          <el-icon :size="36"><ChatDotRound /></el-icon>
        </div>
        <h2 class="start-title">SmartKefu 智能客服</h2>
        <p class="start-desc">选择一个知识库，开始与 AI 对话</p>
        <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" style="margin-bottom: 16px" />
        <div class="kb-list">
          <div
            v-for="kb in kbs"
            :key="kb.id"
            class="kb-item"
            :class="{ active: kbId === kb.id }"
            @click="selectKb(kb.id)"
          >
            <div class="kb-item-icon"><el-icon><ChatDotRound /></el-icon></div>
            <span class="kb-item-name">{{ kb.name }}</span>
            <el-icon v-if="kbId === kb.id" class="kb-item-check"><Check /></el-icon>
          </div>
        </div>
        <el-button type="primary" class="start-btn" :disabled="!kbId" @click="startSession">
          开始对话
        </el-button>
      </div>
    </div>

    <!-- 会话中 -->
    <template v-else>
      <!-- 顶部栏：知识库标签 + 操作 -->
      <div class="chat-header">
        <div class="header-left">
          <div class="kb-badge">
            <el-icon :size="14"><ChatDotRound /></el-icon>
            <span>{{ currentKbName }}</span>
          </div>
          <span class="header-status" :class="{ human: humanMode }">
            {{ humanMode ? '人工客服中' : 'AI 在线' }}
          </span>
        </div>
        <div class="header-right">
          <el-button link class="header-btn" @click="newSession">
            <el-icon style="margin-right: 3px"><RefreshRight /></el-icon>新会话
          </el-button>
          <el-button link class="header-btn" @click="showKbPicker = true">
            <el-icon style="margin-right: 3px"><SwitchButton /></el-icon>切换知识库
          </el-button>
        </div>
      </div>

      <!-- 消息区 -->
      <div ref="listEl" class="msg-list">
        <!-- 快捷提问（仅在只有欢迎语时显示） -->
        <div v-if="msgs.length <= 1 && !humanMode" class="suggest-box">
          <div class="suggest-title">你可以试试问：</div>
          <div class="suggest-list">
            <el-button
              v-for="(q, i) in suggestedQuestions"
              :key="i"
              class="suggest-item"
              @click="useSuggestion(q)"
            >{{ q }}</el-button>
          </div>
        </div>

        <div v-for="(m, i) in msgs" :key="i" class="msg-row" :class="m.role">
          <div class="avatar" v-if="m.role === 'ai'">
            <el-icon :size="16"><ChatDotRound /></el-icon>
          </div>
          <div class="bubble">
            <div class="content">{{ m.content || '思考中…' }}</div>
            <el-collapse v-if="m.references.length" v-model="activeRefs" class="refs">
              <el-collapse-item :name="i" :title="`参考来源（${m.references.length}）`">
                <div v-for="r in m.references" :key="r.chunk_id" class="ref-item">
                  文档 {{ r.doc_id }} · 块 {{ r.chunk_id }} · 相关度 {{ r.score.toFixed(3) }}
                  <div class="snippet">{{ r.snippet }}…</div>
                </div>
              </el-collapse-item>
            </el-collapse>
            <el-button v-if="m.suggestHuman && !humanMode" size="small" type="warning" plain
                       class="human-btn" @click="toHuman">
              转人工
            </el-button>
          </div>
          <div class="avatar user" v-if="m.role === 'user'">
            <span>我</span>
          </div>
        </div>
      </div>

      <!-- 输入栏 -->
      <div class="input-bar">
        <el-input
          v-model="question"
          :placeholder="humanMode ? '输入消息，发送给人工客服' : '输入问题，回车发送'"
          :disabled="sending"
          @keyup.enter="send"
          class="msg-input"
        />
        <el-button type="primary" :loading="sending" class="send-btn" @click="send">
          <el-icon style="margin-right: 4px"><Promotion /></el-icon>发送
        </el-button>
        <el-button v-if="humanMode" type="info" plain @click="leaveHuman">退出人工</el-button>
      </div>
    </template>

    <!-- 切换知识库弹窗 -->
    <el-dialog v-model="showKbPicker" title="切换知识库" width="380px" class="kb-picker">
      <p style="color: #86909c; font-size: 13px; margin: 0 0 16px">切换后将开始新的会话，当前对话记录不会保留。</p>
      <div class="picker-list">
        <div
          v-for="kb in kbs"
          :key="kb.id"
          class="picker-item"
          :class="{ active: kbId === kb.id }"
          @click="selectKb(kb.id)"
        >
          <el-icon><ChatDotRound /></el-icon>
          <span>{{ kb.name }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="showKbPicker = false">取消</el-button>
        <el-button type="primary" :disabled="!kbId" @click="startSession">确认切换</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.chat-wrap {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #eef2ff 0%, #f5f7fa 200px);
}

/* ===== 开始界面 ===== */
.start-screen {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.start-card {
  background: #fff;
  border-radius: 16px;
  padding: 36px 32px;
  width: 100%;
  max-width: 440px;
  box-shadow: 0 8px 32px rgba(59, 91, 219, 0.1);
  text-align: center;
}
.start-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, #3b5bdb, #5c7cfa);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(59, 91, 219, 0.3);
}
.start-title {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
  color: #1d2129;
}
.start-desc {
  color: #86909c;
  font-size: 13px;
  margin: 0 0 24px;
}
.kb-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 24px;
  text-align: left;
}
.kb-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid #e8eaf0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}
.kb-item:hover {
  border-color: #3b5bdb;
  background: #f5f8ff;
}
.kb-item.active {
  border-color: #3b5bdb;
  background: #eef2ff;
}
.kb-item-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #4facfe, #00f2fe);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.kb-item-name {
  flex: 1;
  font-weight: 500;
  color: #1d2129;
  font-size: 14px;
}
.kb-item-check {
  color: #3b5bdb;
}
.start-btn {
  width: 100%;
  height: 42px;
  font-size: 15px;
  font-weight: 600;
  background: linear-gradient(135deg, #3b5bdb, #5c7cfa);
  border: none;
}

/* ===== 聊天顶部栏 ===== */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e8eaf0;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.kb-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: linear-gradient(135deg, #eef2ff, #dbe4ff);
  color: #3b5bdb;
  font-size: 13px;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 20px;
}
.header-status {
  font-size: 12px;
  color: #43e97b;
  font-weight: 500;
}
.header-status.human {
  color: #fa709a;
}
.header-right {
  display: flex;
  gap: 4px;
}
.header-btn {
  font-size: 13px;
  color: #4e5969;
}
.header-btn:hover {
  color: #3b5bdb;
}

/* ===== 消息区 ===== */
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.msg-row {
  display: flex;
  margin-bottom: 16px;
  gap: 10px;
  align-items: flex-start;
}
.msg-row.user {
  justify-content: flex-end;
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b5bdb, #5c7cfa);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 12px;
}
.avatar.user {
  background: linear-gradient(135deg, #43e97b, #38f9d7);
  color: #fff;
  font-weight: 600;
}
.bubble {
  max-width: 70%;
  background: #fff;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  border: 1px solid #f0f1f5;
}
.msg-row.user .bubble {
  background: linear-gradient(135deg, #3b5bdb, #5c7cfa);
  color: #fff;
  border: none;
}
.content { white-space: pre-wrap; line-height: 1.6; font-size: 14px; }
.refs { margin-top: 8px; }
.ref-item { font-size: 12px; color: #909399; margin-bottom: 6px; }
.snippet { color: #606266; }
.human-btn { margin-top: 8px; }

/* ===== 快捷提问 ===== */
.suggest-box {
  margin-bottom: 20px;
  padding: 16px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e8eaf0;
}
.suggest-title {
  font-size: 13px;
  color: #86909c;
  margin-bottom: 10px;
  font-weight: 500;
}
.suggest-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.suggest-item {
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 20px;
  background: #f5f7fa;
  border: 1px solid #e8eaf0;
  color: #4e5969;
  height: auto;
}
.suggest-item:hover {
  background: #eef2ff;
  border-color: #3b5bdb;
  color: #3b5bdb;
}

/* ===== 输入栏 ===== */
.input-bar {
  display: flex;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #e8eaf0;
  background: #fff;
}
.msg-input {
  flex: 1;
}
.send-btn {
  font-weight: 600;
  background: linear-gradient(135deg, #3b5bdb, #5c7cfa);
  border: none;
}

/* 切换知识库弹窗 */
.kb-picker :deep(.el-dialog__title) { font-weight: 600; }
.picker-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.picker-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid #e8eaf0;
  border-radius: 10px;
  cursor: pointer;
  color: #4e5969;
  transition: all 0.2s;
}
.picker-item:hover {
  border-color: #3b5bdb;
  background: #f5f8ff;
}
.picker-item.active {
  border-color: #3b5bdb;
  background: #eef2ff;
  color: #3b5bdb;
}
</style>
