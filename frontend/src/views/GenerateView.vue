<template>
  <div class="generate-view">
    <div class="card">
      <h2>生成 PPT</h2>
      <p style="color:#666;margin:0.5rem 0 1.5rem">选择文档，输入需求，AI 自动生成</p>

      <div class="form-group">
        <label class="form-label">选择文档</label>
        <select v-model="selectedDocId" class="form-input">
          <option value="">-- 请选择已上传的文档 --</option>
          <option v-for="doc in documents" :key="doc.id" :value="doc.id"
                  :disabled="doc.status !== 'ready'">
            {{ doc.filename }} ({{ doc.chunk_count }} 块)
          </option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label">PPT 需求描述</label>
        <textarea v-model="prompt" class="form-input" rows="4"
                  placeholder="例如：帮我做一份竞品分析PPT，重点对比市场份额和核心优势"></textarea>
      </div>

      <div class="form-group">
        <label class="form-label">RAG 检索策略</label>
        <select v-model="ragStrategy" class="form-input">
          <option value="basic">基础检索（默认，适合大部分场景）</option>
          <option value="parent_doc">父文档检索（上下文更完整）</option>
          <option value="routing">智能路由（自动选择检索方式）</option>
          <option value="hybrid">混合检索（向量+关键词，最全面）</option>
        </select>
      </div>

      <button class="btn btn-primary" style="width:100%"
              :disabled="!canGenerate || generating" @click="generate">
        {{ generating ? '生成中，请稍候...' : '开始生成 PPT' }}
      </button>

      <!-- 生成状态 -->
      <div class="generate-status" v-if="task">
        <div :class="['status-badge', `status-${task.status}`]">
          {{ statusText }}
        </div>

        <div v-if="task.status === 'running'" class="progress-hint">
          <div class="spinner"></div>
          <span>Agent 正在检索文档、规划PPT结构并生成文件，请耐心等待...</span>
        </div>

        <div v-if="task.status === 'done'" class="download-section">
          <p>PPT 生成完成！</p>
          <button class="btn btn-primary" @click="download">下载 PPTX</button>
        </div>

        <div v-if="task.status === 'failed'" class="error-section">
          <p>生成失败: {{ task.error_msg }}</p>
        </div>
      </div>
    </div>

    <!-- 快捷需求模板 -->
    <div class="card">
      <h3>快捷模板</h3>
      <div class="template-list">
        <button class="template-btn" v-for="t in templates" :key="t.label"
                @click="prompt = t.value">
          {{ t.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getDocuments, generatePPT, getTaskStatus, downloadPPT } from '../api'

const documents = ref([])
const selectedDocId = ref('')
const prompt = ref('')
const ragStrategy = ref('basic')
const generating = ref(false)
const task = ref(null)
let pollTimer = null

const canGenerate = computed(() => selectedDocId.value && prompt.value.trim())

const statusText = computed(() => {
  const map = { pending: '等待中', running: '生成中', done: '已完成', failed: '失败' }
  return map[task.value?.status] || ''
})

const templates = [
  { label: '竞品分析', value: '帮我做一份竞品分析PPT，重点对比市场份额、核心优势和差异化策略' },
  { label: '季度总结', value: '基于文档数据，生成一份季度工作总结PPT，包含核心成果、数据亮点和下季度计划' },
  { label: '产品介绍', value: '生成一份产品介绍PPT，包含产品定位、核心功能、用户价值和竞争优势' },
  { label: '行业研究', value: '基于文档内容，生成一份行业研究PPT，包含市场概况、发展趋势和机会分析' },
]

async function generate() {
  if (!canGenerate.value) return
  generating.value = true
  task.value = null

  try {
    const res = await generatePPT(selectedDocId.value, prompt.value, ragStrategy.value)
    task.value = res.data
    // 如果是同步返回（已完成或失败），不需要轮询
    if (task.value.status === 'running' || task.value.status === 'pending') {
      startPolling(task.value.id)
    }
  } catch (err) {
    alert('生成失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    generating.value = false
  }
}

function startPolling(taskId) {
  pollTimer = setInterval(async () => {
    try {
      const res = await getTaskStatus(taskId)
      task.value = res.data
      if (task.value.status === 'done' || task.value.status === 'failed') {
        clearInterval(pollTimer)
      }
    } catch (err) {
      clearInterval(pollTimer)
    }
  }, 3000)
}

async function download() {
  if (!task.value?.id) return
  try {
    const res = await downloadPPT(task.value.id)
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `ppt_${task.value.id}.pptx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    alert('下载失败: ' + (err.response?.data?.detail || err.message))
  }
}

onMounted(async () => {
  try {
    const res = await getDocuments()
    documents.value = res.data
  } catch (err) {
    console.error(err)
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.generate-status {
  margin-top: 1.5rem;
  padding: 1.5rem;
  background: #f9f9f9;
  border-radius: 8px;
}

.progress-hint {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  margin-top: 1rem;
  color: #1565c0;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 3px solid #e3f2fd;
  border-top: 3px solid #1565c0;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.download-section {
  margin-top: 1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.error-section {
  margin-top: 1rem;
  color: #c62828;
}

.template-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  margin-top: 1rem;
}

.template-btn {
  padding: 0.5rem 1.2rem;
  border: 2px solid #e0e0e0;
  border-radius: 20px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.95rem;
}

.template-btn:hover {
  border-color: #4fc3f7;
  color: #4fc3f7;
}
</style>
