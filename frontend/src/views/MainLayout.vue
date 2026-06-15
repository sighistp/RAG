<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const chatStore = useChatStore()

const activePage = computed(() => {
  if (route.name === 'files') return 'files'
  if (route.name === 'knowledge') return 'knowledge'
  if (route.name === 'analytics') return 'analytics'
  return 'chat'
})

onMounted(async () => {
  await chatStore.loadConversations()
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

function formatTime(ts: string) {
  if (!ts) return ''
  const d = new Date(ts)
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
          <span class="brand-text">RAG 知识库</span>
        </div>
      </div>

      <div class="sidebar-content">
        <el-button
          type="primary"
          class="new-chat-btn"
          @click="newConversation"
        >
          <el-icon><Plus /></el-icon>
          新建对话
        </el-button>

        <div class="section-title">对话历史</div>

        <div class="conversation-list">
          <div
            v-for="conv in chatStore.conversations"
            :key="conv.id"
            :class="['conv-item', { active: conv.id === chatStore.currentConvId }]"
            @click="selectConversation(conv.id)"
          >
            <div class="conv-icon">
              <el-icon><ChatDotRound /></el-icon>
            </div>
            <div class="conv-info">
              <div class="conv-title">{{ conv.title || '新对话' }}</div>
              <div class="conv-time">{{ formatTime(conv.created_at) }}</div>
            </div>
            <el-button
              class="conv-delete"
              size="small"
              circle
              @click.stop="deleteConversation(conv.id)"
            >
              <el-icon><Close /></el-icon>
            </el-button>
          </div>

          <div v-if="!chatStore.conversations.length" class="empty-conv">
            <el-icon><ChatLineRound /></el-icon>
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
          <el-button class="settings-btn" circle>
            <el-icon><Setting /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="logout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </aside>

    <!-- Main content -->
    <main class="main">
      <div class="topbar">
        <div class="topbar-title">
          {{ chatStore.currentConversation?.title || '新对话' }}
        </div>
        <nav class="topbar-nav">
          <button
            v-for="item in [
              { key: 'chat', label: '对话', icon: 'ChatDotRound' },
              { key: 'files', label: '文件', icon: 'Document' },
              { key: 'knowledge', label: '知识库', icon: 'Collection' },
              { key: 'analytics', label: '分析', icon: 'DataAnalysis' }
            ]"
            :key="item.key"
            :class="['nav-item', { active: activePage === item.key }]"
            @click="switchPage(item.key)"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            {{ item.label }}
          </button>
        </nav>
      </div>

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
}

/* ── Sidebar ──────────────────────────────────────────── */
.sidebar {
  width: var(--sidebar-width);
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  padding: var(--space-5) var(--space-5) var(--space-4);
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
  background: var(--color-accent);
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
  font-weight: var(--font-bold);
  font-family: var(--font-mono);
}

.brand-text {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
}

.sidebar-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
  overflow: hidden;
}

.new-chat-btn {
  width: 100%;
  height: 40px;
  margin-bottom: var(--space-4);
  font-weight: var(--font-medium);
}

.section-title {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wider);
  color: var(--color-secondary);
  padding: var(--space-2) var(--space-2);
  margin-bottom: var(--space-2);
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-3);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  margin-bottom: 2px;
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
}

.conv-delete {
  opacity: 0;
  transition: opacity var(--duration-fast);
}

.conv-item:hover .conv-delete {
  opacity: 1;
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
  background: var(--color-warning-light);
  color: var(--color-warning);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
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
  border: none;
  background: none;
  color: var(--color-secondary);
}

/* ── Main Content ─────────────────────────────────────── */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--color-background);
}

/* ── Topbar ───────────────────────────────────────────── */
.topbar {
  height: var(--topbar-height);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  padding: 0 var(--space-6);
  gap: var(--space-4);
}

.topbar-title {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
  flex: 1;
}

.topbar-nav {
  display: flex;
  gap: 2px;
  background: var(--color-muted);
  border-radius: var(--radius);
  padding: 3px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
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
}

/* ── Page Content ─────────────────────────────────────── */
.page-content {
  flex: 1;
  overflow: hidden;
}

/* ── Responsive ───────────────────────────────────────── */
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    z-index: 100;
    transform: translateX(-100%);
    transition: transform var(--duration-slow) var(--ease-out);
  }

  .sidebar.open {
    transform: translateX(0);
  }
}
</style>
