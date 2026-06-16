<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import { useFilesStore } from '../stores/files'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const chatStore = useChatStore()
const filesStore = useFilesStore()

const activePage = computed(() => {
  if (route.name === 'files') return 'files'
  if (route.name === 'knowledge') return 'knowledge'
  if (route.name === 'analytics') return 'analytics'
  return 'chat'
})

onMounted(async () => {
  await Promise.all([
    chatStore.loadConversations(),
    filesStore.loadFiles()
  ])
})

function switchPage(page: string) {
  router.push(page === 'chat' ? '/' : `/${page}`)
}

async function newConversation() {
  await chatStore.createConversation()
  router.push('/')
}

async function selectConversation(id: number) {
  await chatStore.selectConversation(id)
  router.push(`/chat/${id}`)
}

async function deleteConversation(id: number) {
  await chatStore.deleteConversation(id)
}

function logout() {
  authStore.logout()
  router.push('/login')
}

function formatTime(ts: string | number) {
  if (!ts) return ''
  // Handle Unix timestamps (numbers) and ISO strings
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="brand">
          <div class="brand-icon">R</div>
          <div class="brand-text">
            <span class="brand-name">RAG 知识库</span>
            <span class="brand-version">v3.0</span>
          </div>
        </div>
      </div>

      <div class="sidebar-body">
        <button class="new-chat-btn" @click="newConversation">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="8" y1="2" x2="8" y2="14"/>
            <line x1="2" y1="8" x2="14" y2="8"/>
          </svg>
          新建对话
        </button>

        <!-- File Selector -->
        <div class="section-label">检索范围</div>
        <div class="file-select-list">
          <div
            :class="['file-select-item', { active: chatStore.selectedFile === null }]"
            @click="chatStore.selectFile(null)"
          >
            <div class="file-select-icon">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="5.5" cy="5.5" r="4.5"/>
                <line x1="9" y1="9" x2="13" y2="13"/>
              </svg>
            </div>
            <span class="file-select-name">全部文件</span>
          </div>
          <div
            v-for="file in filesStore.files"
            :key="file.name"
            :class="['file-select-item', { active: chatStore.selectedFile === file.name }]"
            @click="chatStore.selectFile(file.name)"
          >
            <div class="file-select-icon file-icon">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M3 1h5l3 3v8a1 1 0 01-1 1H3a1 1 0 01-1-1V2a1 1 0 011-1z"/>
                <path d="M8 1v3h3"/>
              </svg>
            </div>
            <span class="file-select-name" :title="file.name">{{ file.name }}</span>
          </div>
        </div>

        <div class="section-label">对话历史</div>

        <div class="conv-list">
          <div
            v-for="conv in chatStore.conversations"
            :key="conv.id"
            :class="['conv-item', { active: conv.id === chatStore.currentConvId }]"
            @click="selectConversation(conv.id)"
          >
            <div class="conv-icon">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M2 3h12v8H4l-2 2V3z"/>
              </svg>
            </div>
            <div class="conv-info">
              <div class="conv-title">{{ conv.title || '新对话' }}</div>
              <div class="conv-time">{{ formatTime(conv.created_at) }}</div>
            </div>
            <button class="conv-delete" @click.stop="deleteConversation(conv.id)" title="删除">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                <line x1="3" y1="3" x2="11" y2="11"/>
                <line x1="11" y1="3" x2="3" y2="11"/>
              </svg>
            </button>
          </div>

          <div v-if="!chatStore.conversations.length" class="empty-conv">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
            </svg>
            <span>暂无对话</span>
          </div>
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="user-avatar">
          {{ authStore.user?.username?.[0]?.toUpperCase() || 'U' }}
        </div>
        <div class="user-info">
          <div class="user-name">{{ authStore.user?.username || '用户' }}</div>
        </div>
        <el-dropdown trigger="click">
          <button class="settings-btn" title="设置">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="8" cy="8" r="2.5"/>
              <path d="M13.5 8a5.5 5.5 0 01-.3 1.8l1.2.7-.8 1.4-1.2-.5a5.5 5.5 0 01-1.5 1l.2 1.3h-1.6l.2-1.3a5.5 5.5 0 01-1.5-1l-1.2.5-.8-1.4 1.2-.7A5.5 5.5 0 016 8a5.5 5.5 0 01.3-1.8l-1.2-.7.8-1.4 1.2.5a5.5 5.5 0 011.5-1L8.4 2.3h1.6l-.2 1.3a5.5 5.5 0 011.5 1l1.2-.5.8 1.4-1.2.7c.2.6.3 1.2.3 1.8z"/>
            </svg>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </aside>

    <!-- Main -->
    <main class="main">
      <header class="topbar">
        <div class="topbar-left">
          <h1 class="page-title">{{ chatStore.currentConversation?.title || '新对话' }}</h1>
        </div>
        <nav class="topbar-nav">
          <button
            v-for="item in [
              { key: 'chat', label: '对话' },
              { key: 'files', label: '文件' },
              { key: 'knowledge', label: '知识库' },
              { key: 'analytics', label: '分析' }
            ]"
            :key="item.key"
            :class="['nav-item', { active: activePage === item.key }]"
            @click="switchPage(item.key)"
          >
            {{ item.label }}
          </button>
        </nav>
      </header>

      <div class="page-content">
        <router-view />
      </div>
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--color-background);
}

/* ── Sidebar ──────────────────────────────────────────── */
.sidebar {
  width: var(--sidebar-width);
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  animation: slideInLeft 0.4s var(--ease-out);
}

.sidebar-header {
  padding: var(--space-5) var(--space-5);
  border-bottom: 1px solid var(--color-border);
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.brand-icon {
  width: 36px;
  height: 36px;
  background: var(--color-foreground);
  color: white;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: var(--font-bold);
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-family: var(--font-heading);
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
}

.brand-version {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-secondary);
}

.sidebar-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
  overflow: hidden;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  height: 44px;
  background: var(--color-foreground);
  color: white;
  border: none;
  border-radius: var(--radius);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  font-family: var(--font-body);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  margin-bottom: var(--space-5);
}

.new-chat-btn:hover {
  background: var(--color-primary);
  transform: translateY(-1px);
  box-shadow: var(--shadow);
}

.section-label {
  font-size: 11px;
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-secondary);
  padding: 0 var(--space-3);
  margin-bottom: var(--space-3);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.conv-item:hover {
  background: var(--color-muted);
}

.conv-item.active {
  background: var(--color-accent-light);
}

.conv-icon {
  width: 32px;
  height: 32px;
  background: var(--color-muted);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-secondary);
  flex-shrink: 0;
  transition: all var(--duration-fast);
}

.conv-item.active .conv-icon {
  background: var(--color-accent);
  color: white;
}

.conv-info {
  flex: 1;
  min-width: 0;
}

.conv-title {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--color-foreground);
}

.conv-time {
  font-size: var(--text-xs);
  color: var(--color-secondary);
  margin-top: 2px;
}

.conv-delete {
  opacity: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  color: var(--color-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast);
  flex-shrink: 0;
}

.conv-item:hover .conv-delete {
  opacity: 1;
}

.conv-delete:hover {
  background: var(--color-destructive-light);
  color: var(--color-destructive);
}

.empty-conv {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-8) var(--space-4);
  color: var(--color-secondary);
  font-size: var(--text-sm);
}

/* ── File Selector ───────────────────────────────────── */
.file-select-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin-bottom: var(--space-4);
  max-height: 160px;
  overflow-y: auto;
}

.file-select-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  font-size: var(--text-xs);
  color: var(--color-secondary);
}

.file-select-item:hover {
  background: var(--color-muted);
  color: var(--color-foreground);
}

.file-select-item.active {
  background: var(--color-accent-light);
  color: var(--color-accent);
  font-weight: var(--font-medium);
}

.file-select-icon {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.file-select-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

/* ── Sidebar Footer ───────────────────────────────────── */
.sidebar-footer {
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.user-avatar {
  width: 36px;
  height: 36px;
  background: var(--color-accent-light);
  color: var(--color-accent);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  font-family: var(--font-heading);
}

.user-info {
  flex: 1;
}

.user-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-foreground);
}

.settings-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  color: var(--color-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.settings-btn:hover {
  background: var(--color-muted);
  color: var(--color-foreground);
}

/* ── Main ─────────────────────────────────────────────── */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ── Topbar ───────────────────────────────────────────── */
.topbar {
  height: var(--topbar-height);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
}

.topbar-left {
  flex: 1;
}

.page-title {
  font-family: var(--font-heading);
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
}

.topbar-nav {
  display: flex;
  gap: var(--space-1);
  background: var(--color-muted);
  border-radius: var(--radius);
  padding: 4px;
}

.nav-item {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-secondary);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  border: none;
  background: none;
  font-family: var(--font-body);
}

.nav-item:hover {
  color: var(--color-foreground);
}

.nav-item.active {
  background: var(--color-surface);
  color: var(--color-foreground);
  box-shadow: var(--shadow-xs);
  font-weight: var(--font-semibold);
}

/* ── Page Content ─────────────────────────────────────── */
.page-content {
  flex: 1;
  overflow: hidden;
}

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    z-index: 100;
    transform: translateX(-100%);
    transition: transform var(--duration-slow) var(--ease-out);
  }
  .sidebar.open { transform: translateX(0); }
}
</style>
