import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

let currentUser = localStorage.getItem('ppt_user') || ''

export function setUser(email) {
  currentUser = email
  localStorage.setItem('ppt_user', email)
}

export function getUser() {
  return currentUser
}

api.interceptors.request.use((config) => {
  if (currentUser) {
    config.headers.Authorization = `Bearer ${currentUser}`
  }
  return config
})

// ========== 文档 ==========

export function uploadDocument(file) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getDocuments() {
  return api.get('/documents/')
}

export function deleteDocument(docId) {
  return api.delete(`/documents/${docId}`)
}

// ========== 对话式 Chat ==========

export function createChatSession(documentId, ragStrategy = 'basic') {
  return api.post('/chat/sessions', {
    document_id: documentId,
    rag_strategy: ragStrategy,
  })
}

export function listChatSessions() {
  return api.get('/chat/sessions')
}

export function getChatSession(sessionId) {
  return api.get(`/chat/sessions/${sessionId}`)
}

export function sendMessage(sessionId, content) {
  return api.post(`/chat/sessions/${sessionId}/message`, { content })
}

export function generateFromChat(sessionId) {
  return api.post(`/chat/sessions/${sessionId}/generate`)
}

export function deleteChatSession(sessionId) {
  return api.delete(`/chat/sessions/${sessionId}`)
}

// ========== 任务 / 下载 ==========

export function getTaskStatus(taskId) {
  return api.get(`/tasks/${taskId}`)
}

export function downloadPPT(taskId) {
  return api.get(`/tasks/${taskId}/download`, { responseType: 'blob' })
}
