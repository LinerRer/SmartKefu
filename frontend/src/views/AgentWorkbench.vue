<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api'
import { useUserStore } from '../stores/user'

interface ChatMsg { role: string; content: string }

const userStore = useUserStore()

const queue = ref<any[]>([])          // 排队等待接管的会话
const mine = ref<any[]>([])           // 我已接管的会话
const activeId = ref<number | null>(null)   // 当前正在处理的会话
const msgs = reactive<Record<number, ChatMsg[]>>({})  // 每个会话一份消息数组
const draft = ref('')
const ws = ref<WebSocket | null>(null)
let queueTimer: number | null = null

// ===== 数据拉取 =====
async function loadQueue() {
  const res: any = await http.get('/agent/queue')
  queue.value = res.data
}
async function loadMine() {
  const res: any = await http.get('/agent/conversations')
  mine.value = res.data
}
async function openConv(convId: number) {
  activeId.value = convId
  if (!msgs[convId]) {
    const res: any = await http.get(`/agent/conversations/${convId}/messages`)
    msgs[convId] = res.data.map((m: any) => ({ role: m.role, content: m.content }))
  }
}

// ===== WebSocket =====
function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${proto}://${location.host}/api/v1/ws/agent/${userStore.userId}?token=${encodeURIComponent(userStore.token)}`
  const sock = new WebSocket(url)
  sock.onopen = () => ElMessage.success('坐席通道已连接')
  sock.onmessage = (e) => {
    const msg = JSON.parse(e.data)
    if (msg.type === 'visitor_message') {
      if (!msgs[msg.conversation_id]) msgs[msg.conversation_id] = []
      msgs[msg.conversation_id].push({ role: 'visitor', content: msg.text })
    } else if (msg.type === 'accept_result') {
      if (msg.ok) {
        ElMessage.success(`已接管会话 ${msg.conversation_id}`)
        loadQueue()
        loadMine()
        openConv(msg.conversation_id)
      } else {
        ElMessage.warning('接管失败：该会话可能已被其他坐席接走')
        loadQueue()
      }
    } else if (msg.type === 'system') {
      ElMessage.info(msg.text)
      if (msg.conversation_id) { loadMine(); openConv(msg.conversation_id) }
    } else if (msg.type === 'end_result') {
      if (msg.ok) {
        ElMessage.success(`会话 ${msg.conversation_id} 已结束人工`)
        if (activeId.value === msg.conversation_id) activeId.value = null
        loadMine()
      } else {
        ElMessage.warning('结束失败：该会话不在人工模式')
      }
    } else if (msg.type === 'conversation_closed') {
      ElMessage.info(msg.text)
      if (activeId.value === msg.conversation_id) activeId.value = null
      loadMine()
    } else if (msg.type === 'error') {
      ElMessage.error(msg.text)
    }
  }
  sock.onclose = () => ElMessage.warning('坐席通道断开')
  ws.value = sock
}

async function accept(convId: number) {
  ws.value?.send(JSON.stringify({ type: 'accept', conversation_id: convId }))
}

function reply() {
  const text = draft.value.trim()
  if (!text || activeId.value === null) return
  ws.value?.send(JSON.stringify({ type: 'message', conversation_id: activeId.value, text }))
  if (!msgs[activeId.value]) msgs[activeId.value] = []
  msgs[activeId.value].push({ role: 'agent', content: text })   // 本地先上屏
  draft.value = ''
}

function endConv() {
  if (activeId.value === null) return
  ws.value?.send(JSON.stringify({ type: 'end', conversation_id: activeId.value }))
}

onMounted(() => {
  connect()
  loadQueue()
  loadMine()
  queueTimer = window.setInterval(loadQueue, 5000)   // 轮询队列，新排队会话及时出现
})
onBeforeUnmount(() => {
  ws.value?.close()
  if (queueTimer !== null) clearInterval(queueTimer)
})
</script>

<template>
  <div class="workbench">
    <!-- 左栏：排队 + 我的会话 -->
    <aside class="side">
      <h3>排队中（{{ queue.length }}）</h3>
      <div v-if="!queue.length" class="empty">暂无排队</div>
      <div v-for="q in queue" :key="q.conversation_id" class="row">
        <span>会话 #{{ q.conversation_id }}</span>
        <el-button size="small" type="primary" @click="accept(q.conversation_id)">
          接管
        </el-button>
      </div>

      <el-divider />
      <h3>我的会话（{{ mine.length }}）</h3>
      <div v-for="c in mine" :key="c.conversation_id" class="row"
           :class="{ active: activeId === c.conversation_id }"
           @click="openConv(c.conversation_id)">
        会话 #{{ c.conversation_id }}
      </div>
    </aside>

    <!-- 右栏：聊天区 -->
    <main class="chat">
      <template v-if="activeId !== null">
        <div class="msg-list">
          <div v-for="(m, i) in msgs[activeId] || []" :key="i"
               class="msg-row" :class="m.role">
            <div class="bubble">
              <span v-if="m.role === 'ai'" class="tag">AI</span>
              {{ m.content }}
            </div>
          </div>
        </div>
        <div class="input-bar">
          <el-input v-model="draft" placeholder="回复访客，回车发送"
                    @keyup.enter="reply" />
          <el-button type="primary" @click="reply">发送</el-button>
          <el-button type="info" plain @click="endConv">结束人工</el-button>
        </div>
      </template>
      <div v-else class="placeholder">从左侧选择一个会话开始处理</div>
    </main>
  </div>
</template>

<style scoped>
.workbench { display: flex; height: 100%; }
.side {
  width: 260px;
  border-right: 1px solid #e4e7ed;
  padding: 16px;
  overflow-y: auto;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
}
.row:hover { background: #f5f7fa; }
.row.active { background: #ecf5ff; }
.empty, .placeholder { color: #909399; font-size: 13px; padding: 8px 0; }
.placeholder { margin: auto; }
.chat { flex: 1; display: flex; flex-direction: column; }
.msg-list { flex: 1; overflow-y: auto; padding: 16px; background: #f5f7fa; }
.msg-row { display: flex; margin-bottom: 12px; }
.msg-row.agent { justify-content: flex-end; }
.msg-row.ai { justify-content: flex-start; }
.bubble {
  max-width: 70%;
  background: #fff;
  border-radius: 8px;
  padding: 10px 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.msg-row.agent .bubble { background: #67c23a; color: #fff; }
.tag { font-size: 11px; color: #909399; margin-right: 6px; }
.input-bar {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
  background: #fff;
}
</style>
