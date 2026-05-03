<template>
  <div class="app">
    <nav class="navbar">
      <div class="nav-brand">PPT Agent</div>
      <div class="nav-links">
        <router-link to="/">上传文档</router-link>
        <router-link to="/chat">对话生成</router-link>
        <router-link to="/history">历史记录</router-link>
      </div>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
</script>

<style>
.app {
  min-height: 100vh;
}

.navbar {
  background: #1a1a2e;
  color: white;
  padding: 0 2rem;
  display: flex;
  align-items: center;
  height: 60px;
  gap: 2rem;
}

.nav-brand {
  font-size: 1.3rem;
  font-weight: bold;
  color: #4fc3f7;
}

.nav-links {
  display: flex;
  gap: 1.5rem;
}

.nav-links a {
  color: #ccc;
  text-decoration: none;
  font-size: 0.95rem;
  transition: color 0.2s;
}

.nav-links a:hover,
.nav-links a.router-link-active {
  color: #4fc3f7;
}

.main-content {
  max-width: 900px;
  margin: 2rem auto;
  padding: 0 1rem;
}

/* 通用样式 */
.card {
  background: white;
  border-radius: 12px;
  padding: 2rem;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  margin-bottom: 1.5rem;
}

.btn {
  padding: 0.7rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: #4fc3f7;
  color: white;
}

.btn-primary:hover {
  background: #29b6f6;
}

.btn-primary:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.form-input {
  width: 100%;
  padding: 0.7rem 1rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus {
  border-color: #4fc3f7;
}

.form-label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
  color: #333;
}

.form-group {
  margin-bottom: 1.2rem;
}

.status-badge {
  display: inline-block;
  padding: 0.2rem 0.8rem;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 500;
}

.status-ready { background: #e8f5e9; color: #2e7d32; }
.status-done { background: #e8f5e9; color: #2e7d32; }
.status-pending { background: #fff3e0; color: #e65100; }
.status-running { background: #e3f2fd; color: #1565c0; }
.status-failed { background: #ffebee; color: #c62828; }
.status-uploading { background: #fff3e0; color: #e65100; }
</style>
