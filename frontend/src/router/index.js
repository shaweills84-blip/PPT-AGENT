import { createRouter, createWebHashHistory } from 'vue-router'
import UploadView from '../views/UploadView.vue'
import ChatView from '../views/ChatView.vue'
import HistoryView from '../views/HistoryView.vue'

const routes = [
  { path: '/', component: UploadView },
  { path: '/chat', component: ChatView },
  { path: '/history', component: HistoryView },
]

export default createRouter({
  history: createWebHashHistory(),
  routes,
})
