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
    <div class="login-card">
      <div class="login-logo">
        <div class="logo-icon">R</div>
      </div>
      <h1 class="login-title">RAG 知识库</h1>
      <p class="login-subtitle">智能文档问答系统</p>

      <div class="login-tabs">
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

      <form @submit.prevent="handleSubmit" class="login-form">
        <div class="form-group">
          <label class="form-label">用户名</label>
          <el-input
            v-model="username"
            placeholder="输入用户名"
            size="large"
          />
        </div>
        <div class="form-group">
          <label class="form-label">密码</label>
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
          class="login-btn"
        >
          {{ isLogin ? '登录' : '注册' }}
        </el-button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--color-background);
  position: relative;
  overflow: hidden;
}

.login-page::before {
  content: '';
  position: absolute;
  top: -200px;
  right: -200px;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, var(--color-accent-light) 0%, transparent 70%);
  opacity: 0.5;
}

.login-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-12) var(--space-10);
  width: 400px;
  max-width: 90vw;
  box-shadow: var(--shadow-lg);
  position: relative;
  z-index: 1;
  animation: slideUp var(--duration-slow) var(--ease-out);
}

.login-logo {
  text-align: center;
  margin-bottom: var(--space-6);
}

.logo-icon {
  width: 56px;
  height: 56px;
  background: var(--color-accent);
  border-radius: var(--radius-lg);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 28px;
  font-weight: var(--font-bold);
  font-family: var(--font-mono);
}

.login-title {
  font-family: var(--font-display);
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  text-align: center;
  margin-bottom: var(--space-1);
  color: var(--color-foreground);
}

.login-subtitle {
  text-align: center;
  font-size: var(--text-base);
  color: var(--color-secondary);
  margin-bottom: var(--space-8);
}

.login-tabs {
  display: flex;
  background: var(--color-muted);
  border-radius: var(--radius);
  padding: 3px;
  margin-bottom: var(--space-6);
}

.tab {
  flex: 1;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  border: none;
  background: none;
  color: var(--color-secondary);
  font-family: var(--font-body);
}

.tab.active {
  background: var(--color-surface);
  color: var(--color-foreground);
  box-shadow: var(--shadow-xs);
}

.form-group {
  margin-bottom: var(--space-4);
}

.form-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-secondary);
  margin-bottom: var(--space-2);
}

.login-btn {
  width: 100%;
  margin-top: var(--space-2);
  height: 44px;
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
}

:deep(.el-input__wrapper) {
  border-radius: var(--radius);
  box-shadow: 0 0 0 1px var(--color-border);
}

:deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--color-secondary);
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px var(--color-accent);
}
</style>
