<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()

const isLogin = ref(true)
const username = ref('')
const password = ref('')
const loading = ref(false)

async function handleSubmit() {
  if (!username.value || !password.value) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    if (isLogin.value) {
      await authStore.login(username.value, password.value)
    } else {
      await authStore.register(username.value, password.value)
    }
    router.push('/')
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '操作失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <!-- Left brand panel -->
    <div class="brand-panel">
      <div class="brand-content">
        <div class="brand-logo">
          <div class="logo-icon">R</div>
          <span class="logo-text">RAGv3</span>
        </div>
        <h1 class="brand-title">智能知识库<br>问答系统</h1>
        <p class="brand-desc">
          基于检索增强生成的企业级知识库，支持多轮对话、Agent 工具调用、多知识库管理。
        </p>
        <div class="brand-pattern">
          <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="100" cy="100" r="80" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
            <circle cx="100" cy="100" r="60" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>
            <circle cx="100" cy="100" r="40" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
            <circle cx="100" cy="100" r="20" fill="rgba(255,255,255,0.05)"/>
            <circle cx="100" cy="100" r="6" fill="rgba(255,255,255,0.3)"/>
            <line x1="100" y1="20" x2="100" y2="180" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
            <line x1="20" y1="100" x2="180" y2="100" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
            <circle cx="100" cy="20" r="3" fill="rgba(255,255,255,0.2)"/>
            <circle cx="100" cy="180" r="3" fill="rgba(255,255,255,0.2)"/>
            <circle cx="20" cy="100" r="3" fill="rgba(255,255,255,0.2)"/>
            <circle cx="180" cy="100" r="3" fill="rgba(255,255,255,0.2)"/>
            <circle cx="43" cy="43" r="3" fill="rgba(255,255,255,0.15)"/>
            <circle cx="157" cy="43" r="3" fill="rgba(255,255,255,0.15)"/>
            <circle cx="43" cy="157" r="3" fill="rgba(255,255,255,0.15)"/>
            <circle cx="157" cy="157" r="3" fill="rgba(255,255,255,0.15)"/>
          </svg>
        </div>
      </div>
    </div>

    <!-- Right login panel -->
    <div class="login-panel">
      <div class="login-card">
        <div class="login-header">
          <h2 class="login-title">{{ isLogin ? '欢迎回来' : '创建账号' }}</h2>
          <p class="login-subtitle">{{ isLogin ? '登录以继续使用知识库' : '注册以开始使用' }}</p>
        </div>

        <div class="tabs">
          <button
            :class="['tab', { active: isLogin }]"
            @click="isLogin = true"
          >
            登录
          </button>
          <button
            :class="['tab', { active: !isLogin }]"
            @click="isLogin = false"
          >
            注册
          </button>
        </div>

        <form @submit.prevent="handleSubmit" class="form">
          <div class="field">
            <label class="label">用户名</label>
            <el-input
              v-model="username"
              placeholder="输入用户名"
              size="large"
            />
          </div>
          <div class="field">
            <label class="label">密码</label>
            <el-input
              v-model="password"
              type="password"
              placeholder="输入密码"
              size="large"
              show-password
            />
          </div>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleSubmit"
            class="submit-btn"
          >
            {{ isLogin ? '登录' : '注册' }}
          </el-button>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background: var(--color-background);
}

/* ── Brand Panel (Left) ───────────────────────────────── */
.brand-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-12);
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  position: relative;
  z-index: 1;
}

.brand-panel::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 120px;
  height: 100%;
  background: linear-gradient(to right, transparent, var(--color-background));
  z-index: 2;
}

.brand-content {
  max-width: 480px;
  animation: slideUp 0.6s var(--ease-out);
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-8);
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: var(--color-accent);
  color: white;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 18px;
  font-weight: var(--font-bold);
}

.logo-text {
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: white;
  letter-spacing: -0.02em;
}

.brand-title {
  font-family: var(--font-heading);
  font-size: clamp(2rem, 4vw, 2.75rem);
  font-weight: var(--font-bold);
  color: white;
  line-height: 1.2;
  margin-bottom: var(--space-6);
  letter-spacing: -0.02em;
}

.brand-desc {
  font-size: var(--text-base);
  color: rgba(255, 255, 255, 0.6);
  line-height: var(--leading-relaxed);
  margin-bottom: var(--space-10);
}

.brand-pattern {
  width: 200px;
  height: 200px;
  opacity: 0.6;
  animation: spin 30s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ── Login Panel (Right) ──────────────────────────────── */
.login-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-12);
  background: var(--color-background);
  position: relative;
  z-index: 1;
}

.login-card {
  width: 400px;
  max-width: 100%;
  animation: slideUp 0.6s var(--ease-out);
  animation-delay: 0.1s;
  animation-fill-mode: both;
}

.login-header {
  margin-bottom: var(--space-8);
}

.login-title {
  font-family: var(--font-heading);
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--color-foreground);
  margin-bottom: var(--space-2);
}

.login-subtitle {
  font-size: var(--text-base);
  color: var(--color-secondary);
}

/* ── Tabs ─────────────────────────────────────────────── */
.tabs {
  display: flex;
  gap: var(--space-1);
  margin-bottom: var(--space-8);
  border-bottom: 1px solid var(--color-border);
  padding-bottom: var(--space-1);
}

.tab {
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-secondary);
  background: none;
  border: none;
  cursor: pointer;
  position: relative;
  transition: color var(--duration-normal) var(--ease-out);
  font-family: var(--font-body);
}

.tab::after {
  content: '';
  position: absolute;
  bottom: calc(-1 * var(--space-1) - 1px);
  left: 0;
  right: 0;
  height: 2px;
  background: var(--color-accent);
  transform: scaleX(0);
  transition: transform var(--duration-normal) var(--ease-out);
}

.tab.active {
  color: var(--color-accent);
  font-weight: var(--font-semibold);
}

.tab.active::after {
  transform: scaleX(1);
}

/* ── Form ─────────────────────────────────────────────── */
.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-foreground);
}

.submit-btn {
  width: 100%;
  height: 48px;
  font-size: var(--text-base) !important;
  font-weight: var(--font-semibold) !important;
  margin-top: var(--space-2);
}

/* ── Responsive ───────────────────────────────────────── */
@media (max-width: 768px) {
  .login-page {
    flex-direction: column;
  }

  .brand-panel {
    padding: var(--space-8) var(--space-6);
    min-height: auto;
  }

  .brand-panel::before {
    display: none;
  }

  .brand-stats {
    gap: var(--space-6);
  }

  .login-panel {
    padding: var(--space-8) var(--space-6);
  }
}

/* ── Animations ───────────────────────────────────────── */
@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
