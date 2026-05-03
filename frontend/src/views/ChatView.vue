<template>
  <div class="chat-layout">
    <!-- 左侧：会话列表 -->
    <aside class="sidebar">
      <button class="btn-new-chat" @click="startNewChat">+ 新建对话</button>

      <div class="session-list">
        <div
          v-for="s in sessions"
          :key="s.session_id"
          :class="['session-item', { active: s.session_id === currentSessionId }]"
          @click="switchSession(s.session_id)"
        >
          <div class="session-preview">{{ s.preview }}</div>
          <div class="session-meta">
            <span :class="['dot', s.stage]"></span>
            {{ stageLabel(s.stage) }}
          </div>
        </div>
        <div v-if="sessions.length === 0" class="empty-hint">暂无对话记录</div>
      </div>
    </aside>

    <!-- 右侧：对话区 -->
    <main class="chat-main">
      <!-- 新建对话：先选文档 -->
      <div class="new-chat-panel card" v-if="showDocPicker">
        <h3>开始新对话</h3>
        <p style="color:#666;margin:0.5rem 0 1.5rem">选择一个已索引的文档，Agent 会基于它与你对话制作 PPT</p>

        <div class="form-group">
          <label class="form-label">选择文档</label>
          <select v-model="newDocId" class="form-input">
            <option value="">-- 请选择 --</option>
            <option v-for="doc in documents" :key="doc.id" :value="doc.id"
                    :disabled="doc.status !== 'ready'">
              {{ doc.filename }} ({{ doc.chunk_count }} 块)
            </option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">检索策略</label>
          <select v-model="newStrategy" class="form-input">
            <option value="basic">基础检索</option>
            <option value="parent_doc">父文档检索</option>
            <option value="routing">智能路由</option>
            <option value="hybrid">混合检索</option>
          </select>
        </div>

        <button class="btn btn-primary" style="width:100%"
                :disabled="!newDocId || creating" @click="createSession">
          {{ creating ? '创建中...' : '开始对话' }}
        </button>

        <p style="margin-top:1rem;font-size:0.85rem;color:#999">
          也可以先去 <router-link to="/">上传文档</router-link>
        </p>
      </div>

      <!-- 对话消息 -->
      <div class="messages-area" ref="messagesArea" v-if="currentSessionId && !showDocPicker">
        <div class="message-wrapper" v-for="(msg, i) in messages" :key="i"
             :class="msg.role">
          <div class="message-bubble">
            <div class="msg-content" v-html="renderContent(msg.content)"></div>
            <!-- PPT 结构预览 -->
            <div class="ppt-preview" v-if="msg.role === 'assistant' && extractSlides(msg.content)">
              <div class="preview-title">PPT 结构预览</div>
              <div class="preview-slide" v-for="(s, si) in extractSlides(msg.content)" :key="si">
                <span class="slide-type">{{ s.type }}</span>
                <span class="slide-title">{{ s.title }}</span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="waiting" class="message-wrapper assistant">
          <div class="message-bubble typing">Agent 思考中...</div>
        </div>
      </div>

      <!-- 底部操作栏 -->
      <div class="bottom-bar" v-if="currentSessionId && !showDocPicker">
        <!-- Stage: generating -->
        <div class="stage-bar generating" v-if="currentStage === 'generating'">
          <div class="spinner"></div>
          <span>Multi-Agent 协作生成中，请稍候...</span>
        </div>

        <!-- Stage: confirmed → 显示生成按钮 -->
        <div class="stage-bar confirmed" v-else-if="currentStage === 'confirmed'">
          <span>结构已确认，可以生成 PPT 了</span>
          <button class="btn btn-primary" @click="triggerGenerate" :disabled="generating">
            {{ generating ? '生成中...' : '确认生成 PPT' }}
          </button>
        </div>

        <!-- Stage: done → 下载 -->
        <div class="stage-bar done" v-else-if="currentStage === 'done'">
          <span>PPT 已生成</span>
          <button class="btn btn-primary" @click="downloadPPTX">下载 PPTX</button>
        </div>

        <!-- Stage: clarifying → 输入框 -->
        <div class="input-row" v-else>
          <input
            v-model="inputText"
            class="form-input chat-input"
            placeholder="输入你的需求，比如：帮我做一份竞品分析PPT..."
            @keyup.enter="sendMsg"
            :disabled="waiting"
          />
          <button class="btn btn-primary" @click="sendMsg" :disabled="!inputText.trim() || waiting">
            发送
          </button>
        </div>
      </div>

      <!-- 空状态 -->
      <div class="empty-state" v-if="!currentSessionId && !showDocPicker">
        <p>选择一个对话或创建新对话</p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import {
  getDocuments,
  listChatSessions, getChatSession,
  createChatSession, sendMessage, generateFromChat,
  downloadPPT,
} from '../api'

// ---- 状态 ----

const sessions = ref([])
const currentSessionId = ref('')
const currentStage = ref('')
const messages = ref([])
const inputText = ref('')
const waiting = ref(false)
const generating = ref(false)
const taskId = ref(null)
const showDocPicker = ref(true)

// 新建会话
const documents = ref([])
const newDocId = ref('')
const newStrategy = ref('basic')
const creating = ref(false)
const messagesArea = ref(null)

// ---- 初始化 ----

onMounted(async () => {
  await loadSessions()
  // 有历史会话直接展示列表，没有则显示文档选择
  if (sessions.value.length > 0) {
    showDocPicker.value = false
  }
})

// ---- 会话管理 ----

async function loadSessions() {
  try {
    const res = await listChatSessions()
    sessions.value = res.data
  } catch (e) {
    console.error('加载会话列表失败', e)
  }
}

async function loadDocuments() {
  try {
    const res = await getDocuments()
    documents.value = res.data
  } catch (e) {
    console.error('加载文档失败', e)
  }
}

function startNewChat() {
  currentSessionId.value = ''
  messages.value = []
  currentStage.value = ''
  taskId.value = null
  showDocPicker.value = true
  loadDocuments()
}

async function createSession() {
  if (!newDocId.value) return
  creating.value = true
  try {
    const res = await createChatSession(newDocId.value, newStrategy.value)
    const sid = res.data.session_id
    showDocPicker.value = false
    await loadSessions()
    await loadSession(sid)
    // Agent 开场白
    messages.value.push({ role: 'assistant', content: res.data.message })
    currentStage.value = 'clarifying'
  } catch (e) {
    alert('创建会话失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

async function switchSession(sid) {
  if (sid === currentSessionId.value) return
  showDocPicker.value = false
  await loadSession(sid)
}

async function loadSession(sid) {
  try {
    const res = await getChatSession(sid)
    currentSessionId.value = sid
    messages.value = res.data.messages || []
    currentStage.value = res.data.stage
    taskId.value = res.data.task_id
    scrollToBottom()
  } catch (e) {
    console.error('加载会话失败', e)
  }
}

// ---- 消息 ----

async function sendMsg() {
  if (!inputText.value.trim() || waiting.value) return
  const text = inputText.value.trim()
  inputText.value = ''
  messages.value.push({ role: 'user', content: text })
  waiting.value = true
  scrollToBottom()

  try {
    const res = await sendMessage(currentSessionId.value, text)
    waiting.value = false
    messages.value.push({ role: 'assistant', content: res.data.reply })
    currentStage.value = res.data.stage

    // 如果 Agent 返回了 ppt_preview，存到最新一条消息的 meta 里
    if (res.data.ppt_preview) {
      const last = messages.value[messages.value.length - 1]
      last._pptPreview = res.data.ppt_preview
    }

    await loadSessions()
    scrollToBottom()
  } catch (e) {
    waiting.value = false
    alert('发送失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function triggerGenerate() {
  generating.value = true
  currentStage.value = 'generating'
  messages.value.push({ role: 'assistant', content: '正在分析文档并生成 PPT，请稍候...' })
  scrollToBottom()

  try {
    const res = await generateFromChat(currentSessionId.value)
    generating.value = false
    taskId.value = res.data.task_id
    currentStage.value = 'done'

    const slideCount = res.data.ppt_data?.slides?.length || 0
    messages.value.push({
      role: 'assistant',
      content: `PPT 已生成完成！共 ${slideCount} 页。你可以下载，也可以继续告诉我需要修改的地方。`,
    })
    await loadSessions()
    scrollToBottom()
  } catch (e) {
    generating.value = false
    currentStage.value = 'clarifying'
    alert('生成失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function downloadPPTX() {
  if (!taskId.value) return
  try {
    const res = await downloadPPT(taskId.value)
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `ppt_${taskId.value}.pptx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    alert('下载失败')
  }
}

// ---- 辅助 ----

function stageLabel(s) {
  const map = { clarifying: '澄清中', confirmed: '已确认', generating: '生成中', done: '已完成' }
  return map[s] || s
}

function extractSlides(content) {
  // 尝试从消息中提取 PPT 结构（Agent 返回的 JSON）
  try {
    // 找 JSON 代码块
    const m = content.match(/```(?:json)?\s*\n?([\s\S]*?)\n?```/)
    if (m) {
      const data = JSON.parse(m[1])
      return data.slides || null
    }
    // 或直接是 JSON
    const trimmed = content.trim()
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      const data = JSON.parse(trimmed)
      return data.slides || null
    }
  } catch {}
  return null
}

function renderContent(text) {
  // 简单 markdown 渲染：代码块、粗体、换行
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
    .replace(/```(?:json)?\s*\n?([\s\S]*?)\n?```/g, '<pre>$1</pre>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/## (.+)/g, '<h4>$1</h4>')
    .replace(/- (.+)/g, '· $1')
  return html
}

function scrollToBottom() {
  nextTick(() => {
    const el = messagesArea.value
    if (el) el.scrollTop = el.scrollHeight
  })
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: calc(100vh - 60px - 4rem);
  gap: 0;
}

/* ---- 侧边栏 ---- */
.sidebar {
  width: 260px;
  min-width: 260px;
  background: #f8f9fa;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.btn-new-chat {
  margin: 1rem;
  padding: 0.6rem;
  border: 2px dashed #ccc;
  border-radius: 8px;
  background: white;
  cursor: pointer;
  font-size: 0.95rem;
  color: #555;
  transition: all 0.2s;
}
.btn-new-chat:hover {
  border-color: #4fc3f7;
  color: #4fc3f7;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 0.5rem;
}

.session-item {
  padding: 0.8rem;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 0.3rem;
  transition: background 0.15s;
}
.session-item:hover { background: #eef1f5; }
.session-item.active { background: #e3f2fd; }

.session-preview {
  font-size: 0.9rem;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  font-size: 0.75rem;
  color: #999;
  margin-top: 0.2rem;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.dot.clarifying { background: #ff9800; }
.dot.confirmed { background: #4fc3f7; }
.dot.generating { background: #1565c0; }
.dot.done { background: #4caf50; }

.empty-hint {
  text-align: center;
  color: #bbb;
  padding: 2rem 0;
  font-size: 0.9rem;
}

/* ---- 对话区 ---- */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
}

.message-wrapper {
  margin-bottom: 1rem;
  display: flex;
}
.message-wrapper.user { justify-content: flex-end; }

.message-bubble {
  max-width: 75%;
  padding: 0.8rem 1.2rem;
  border-radius: 12px;
  font-size: 0.95rem;
  line-height: 1.6;
}
.message-wrapper.user .message-bubble {
  background: #4fc3f7;
  color: white;
  border-bottom-right-radius: 4px;
}
.message-wrapper.assistant .message-bubble {
  background: #f0f2f5;
  color: #333;
  border-bottom-left-radius: 4px;
}

.msg-content :deep(pre) {
  background: rgba(0,0,0,0.06);
  padding: 0.8rem;
  border-radius: 6px;
  font-size: 0.85rem;
  overflow-x: auto;
  margin: 0.5rem 0;
}

.msg-content :deep(h4) {
  margin: 0.5rem 0 0.3rem;
  font-size: 1rem;
}

.typing {
  color: #999;
  font-style: italic;
}

/* PPT 预览卡片 */
.ppt-preview {
  margin-top: 0.8rem;
  padding: 0.8rem;
  background: rgba(0,0,0,0.04);
  border-radius: 8px;
  font-size: 0.85rem;
}

.preview-title {
  font-weight: 600;
  margin-bottom: 0.4rem;
  color: #555;
}

.preview-slide {
  display: flex;
  gap: 0.5rem;
  padding: 0.2rem 0;
}

.slide-type {
  background: #e3f2fd;
  color: #1565c0;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
  min-width: 60px;
  text-align: center;
}

.slide-title {
  color: #555;
}

/* ---- 底部操作栏 ---- */
.bottom-bar {
  padding: 1rem 2rem;
  border-top: 1px solid #eee;
  background: white;
}

.stage-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.5rem 0;
}

.stage-bar.generating { color: #1565c0; }
.stage-bar.confirmed { color: #4caf50; }
.stage-bar.done { color: #4caf50; }

.input-row {
  display: flex;
  gap: 0.8rem;
}
.chat-input { flex: 1; }

.spinner {
  width: 18px;
  height: 18px;
  border: 3px solid #e3f2fd;
  border-top: 3px solid #1565c0;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #bbb;
  font-size: 1.1rem;
}

/* 新建对话面板 */
.new-chat-panel {
  margin: 1rem;
}
</style>
