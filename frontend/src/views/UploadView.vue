<template>
  <div class="upload-view">
    <!-- 用户登录（简化方案） -->
    <div class="card" v-if="!isLoggedIn">
      <h2>欢迎使用 PPT Agent</h2>
      <p style="color:#666;margin:1rem 0">输入邮箱开始使用（演示项目简化登录）</p>
      <div class="form-group">
        <input v-model="email" class="form-input" placeholder="输入邮箱" @keyup.enter="login" />
      </div>
      <button class="btn btn-primary" @click="login">开始使用</button>
    </div>

    <!-- 上传区域 -->
    <div class="card" v-else>
      <h2>上传文档</h2>
      <p style="color:#666;margin:0.5rem 0 1.5rem">支持 PDF、Word、TXT 格式</p>

      <div class="upload-area" @click="triggerFileInput" @dragover.prevent @drop.prevent="onDrop">
        <input ref="fileInput" type="file" accept=".pdf,.docx,.doc,.txt" @change="onFileSelect" hidden />
        <div class="upload-icon">📄</div>
        <p>点击选择文件或拖拽到此处</p>
        <p class="upload-hint" v-if="selectedFile">已选择: {{ selectedFile.name }}</p>
      </div>

      <button class="btn btn-primary" style="margin-top:1rem;width:100%"
              :disabled="!selectedFile || uploading" @click="upload">
        {{ uploading ? '上传中...' : '上传并索引' }}
      </button>

      <div class="upload-result" v-if="uploadResult">
        <div :class="['status-badge', `status-${uploadResult.status}`]">
          {{ uploadResult.status === 'ready' ? '索引完成' : '索引失败' }}
        </div>
        <p v-if="uploadResult.status === 'ready'" style="margin-top:0.5rem">
          切块数量: {{ uploadResult.chunk_count }} |
          <router-link to="/generate">去生成PPT →</router-link>
        </p>
      </div>
    </div>

    <!-- 已上传文档列表 -->
    <div class="card" v-if="isLoggedIn && documents.length">
      <h3>已上传文档</h3>
      <div class="doc-list">
        <div class="doc-item" v-for="doc in documents" :key="doc.id">
          <div>
            <strong>{{ doc.filename }}</strong>
            <span :class="['status-badge', `status-${doc.status}`]" style="margin-left:0.5rem">
              {{ doc.status }}
            </span>
          </div>
          <div style="color:#888;font-size:0.85rem">
            {{ doc.chunk_count }} 块 | {{ formatDate(doc.created_at) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { setUser, getUser, uploadDocument, getDocuments } from '../api'

const email = ref('')
const isLoggedIn = ref(!!getUser())
const selectedFile = ref(null)
const uploading = ref(false)
const uploadResult = ref(null)
const documents = ref([])
const fileInput = ref(null)

function login() {
  if (!email.value.trim()) return
  setUser(email.value.trim())
  isLoggedIn.value = true
  loadDocuments()
}

function triggerFileInput() {
  fileInput.value.click()
}

function onFileSelect(e) {
  selectedFile.value = e.target.files[0]
}

function onDrop(e) {
  selectedFile.value = e.dataTransfer.files[0]
}

async function upload() {
  if (!selectedFile.value) return
  uploading.value = true
  uploadResult.value = null
  try {
    const res = await uploadDocument(selectedFile.value)
    uploadResult.value = res.data
    selectedFile.value = null
    loadDocuments()
  } catch (err) {
    uploadResult.value = { status: 'failed' }
    alert('上传失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    uploading.value = false
  }
}

async function loadDocuments() {
  try {
    const res = await getDocuments()
    documents.value = res.data
  } catch (err) {
    console.error('加载文档失败', err)
  }
}

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  if (isLoggedIn.value) loadDocuments()
})
</script>

<style scoped>
.upload-area {
  border: 2px dashed #ccc;
  border-radius: 12px;
  padding: 3rem 2rem;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s;
}

.upload-area:hover {
  border-color: #4fc3f7;
}

.upload-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.upload-hint {
  color: #4fc3f7;
  margin-top: 0.5rem;
  font-weight: 500;
}

.upload-result {
  margin-top: 1rem;
  padding: 1rem;
  background: #f9f9f9;
  border-radius: 8px;
}

.doc-list {
  margin-top: 1rem;
}

.doc-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.8rem 0;
  border-bottom: 1px solid #f0f0f0;
}

.doc-item:last-child {
  border-bottom: none;
}
</style>
