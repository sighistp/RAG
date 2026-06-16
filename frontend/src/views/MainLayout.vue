<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const activeMenu = computed(() => {
  if (route.path.startsWith('/files')) return 'files'
  if (route.path.startsWith('/kb')) return 'kb'
  if (route.path.startsWith('/analysis')) return 'analysis'
  return 'files'
})

function handleMenuSelect(index: string) {
  router.push(`/${index}`)
}
</script>

<template>
  <div class="layout">
    <header class="topbar">
      <div class="topbar-left">
        <div class="brand">
          <div class="brand-icon">R</div>
          <span class="brand-name">RAG 知识库</span>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        mode="horizontal"
        class="topbar-menu"
        @select="handleMenuSelect"
      >
        <el-menu-item index="files">
          <span class="menu-icon">📄</span>
          <span>文件</span>
        </el-menu-item>
        <el-menu-item index="kb">
          <span class="menu-icon">📚</span>
          <span>知识库</span>
        </el-menu-item>
        <el-menu-item index="analysis">
          <span class="menu-icon">📊</span>
          <span>分析</span>
        </el-menu-item>
      </el-menu>

      <div class="topbar-right">
        <el-dropdown trigger="click">
          <button class="user-btn">
            <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 8a3 3 0 100-6 3 3 0 000 6zm5 6a5 5 0 00-10 0h10z"/>
            </svg>
            <span class="user-name">{{ authStore.user?.username || '用户' }}</span>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M3 5l3 3 3-3"/>
            </svg>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="authStore.logout(); router.push('/login')">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: var(--color-background);
}

/* ── Top Bar ─────────────────────────────────────────── */
.topbar {
  height: var(--topbar-height);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  flex-shrink: 0;
  z-index: 10;
}

.topbar-left {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.brand-icon {
  width: 32px;
  height: 32px;
  background: var(--color-foreground);
  color: white;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: var(--font-bold);
}

.brand-name {
  font-family: var(--font-heading);
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
}

/* ── Menu ────────────────────────────────────────────── */
.topbar-menu {
  border-bottom: none !important;
  background: transparent !important;
  --el-menu-bg-color: transparent;
  --el-menu-hover-bg-color: var(--color-muted);
  --el-menu-active-color: var(--color-accent);
  --el-menu-text-color: var(--color-secondary);
  --el-menu-item-font-size: var(--text-sm);
}

:deep(.el-menu--horizontal > .el-menu-item) {
  height: 40px;
  line-height: 40px;
  border-radius: var(--radius);
  margin: 0 var(--space-1);
  padding: 0 var(--space-4);
  border: none;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

:deep(.el-menu--horizontal > .el-menu-item.is-active) {
  background: var(--color-accent-light) !important;
  color: var(--color-accent) !important;
  font-weight: var(--font-semibold);
}

:deep(.el-menu--horizontal > .el-menu-item:hover) {
  background: var(--color-muted) !important;
}

.menu-icon {
  font-size: 14px;
}

/* ── User ────────────────────────────────────────────── */
.topbar-right {
  flex-shrink: 0;
}

.user-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  color: var(--color-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  font-family: var(--font-body);
}

.user-btn:hover {
  background: var(--color-muted);
  border-color: var(--color-border-hover);
  color: var(--color-foreground);
}

.user-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

/* ── Main ─────────────────────────────────────────────── */
.main {
  flex: 1;
  overflow: hidden;
}
</style>
