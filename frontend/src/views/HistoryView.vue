<template>
  <div class="history-view">
    <div class="card">
      <h2>生成历史</h2>
      <p style="color:#666;margin:0.5rem 0 1.5rem">所有对话会话及生成的 PPT</p>

      <div v-if="sessions.length === 0" style="text-align:center;color:#999;padding:2rem">
        暂无记录，<router-link to="/chat">去创建对话</router-link>
      </div>

      <div class="task-list" v-else>
        <div class="task-item" v-for="s in sessions" :key="s.session_id">
          <div class="task-info">
            <div class="task-prompt">{{ s.preview }}</div>
            <div class="task-meta">
              <span :class="['status-badge', `status-${s.stage === 'done' ? 'done' : 'running'}`]">
                {{ stageLabel(s.stage) }}
              </span>
              {{ formatDate(s.updated_at) }}
            </div>
          </div>
          <div class="task-actions">
            <button class="btn btn-primary" style="padding:0.4rem 1rem;font-size:0.85rem"
                    v-if="s.stage === 'done'" @click="downloadBySession(s.session_id)">
              下载
            </button>
            <router-link :to="'/chat'" style="font-size:0.85rem;color:#4fc3f7">
              查看对话
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listChatSessions, getChatSession, downloadPPT } from '../api'

const sessions = ref([])

function stageLabel(s) {
  const map = { clarifying: '澄清中', confirmed: '已确认', generating: '生成中', done: '已完成' }
  return map[s] || s
}

function formatDate(ts) {
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

async function downloadBySession(sessionId) {
  try {
    const res = await getChatSession(sessionId)
    const taskId = res.data.task_id
    if (!taskId) return alert('未找到关联任务')

    const dl = await downloadPPT(taskId)
    const url = URL.createObjectURL(dl.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `ppt_${taskId}.pptx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    alert('下载失败')
  }
}

onMounted(async () => {
  try {
    const res = await listChatSessions()
    sessions.value = res.data
  } catch (err) {
    console.error(err)
  }
})
</script>

<style scoped>
.task-list {
  margin-top: 0.5rem;
}

.task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 0;
  border-bottom: 1px solid #f0f0f0;
}

.task-item:last-child {
  border-bottom: none;
}

.task-prompt {
  font-weight: 500;
  margin-bottom: 0.3rem;
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-meta {
  font-size: 0.85rem;
  color: #888;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}
</style>
