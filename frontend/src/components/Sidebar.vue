<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useChatStore, type ChatMode } from '../stores/chat'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const chatStore = useChatStore()

const currentMode = computed<ChatMode>(() => {
  const m = route.path.match(/\/mode\/(\w+)/)
  return (m?.[1] as ChatMode) || 'file'
})

// Sync route-derived mode to store, reload conversations, clear file selection
watch(currentMode, (newMode, oldMode) => {
  chatStore.currentMode = newMode
  if (newMode !== oldMode) {
    chatStore.selectFile(null)
    chatStore.loadConversations(newMode, true)
  }
}, { immediate: true })

const modes: Array<{ key: ChatMode; icon: string; label: string }> = [
  { key: 'file', icon: '📄', label: '文件' },
  { key: 'kb', icon: '📚', label: '知识库' },
  { key: 'analysis', icon: '📊', label: '分析' }
]

function switchMode(mode: ChatMode) {
  router.push(`/mode/${mode}`)
}

async function newConversation() {
  await chatStore.createConversation(currentMode.value)
  router.push(`/mode/${currentMode.value}`)
}

async function selectConversation(id: number) {
  await chatStore.selectConversation(id)
}

async function deleteConversation(id: number) {
  await chatStore.deleteConversation(id)
}

function formatTime(ts: string | number) {
  if (!ts) return ''
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<template>
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
      <!-- Mode switcher -->
      <div class="mode-switcher">
        <button
          v-for="m in modes"
          :key="m.key"
          :class="['mode-btn', { active: currentMode === m.key }]"
          @click="switchMode(m.key)"
        >
          <span class="mode-icon">{{ m.icon }}</span>
          <span class="mode-label">{{ m.label }}</span>
        </button>
      </div>

      <div class="sidebar-divider"></div>

      <!-- New conversation button -->
      <button class="new-chat-btn" @click="newConversation">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="8" y1="2" x2="8" y2="14"/>
          <line x1="2" y1="8" x2="14" y2="8"/>
        </svg>
        新建对话
      </button>

      <!-- Conversation list filtered by mode -->
      <div class="conv-section-label">对话历史</div>

      <div class="conv-list">
        <div
          v-for="conv in chatStore.conversationsByMode(currentMode).value"
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

        <div v-if="!chatStore.conversationsByMode(currentMode).value.length" class="empty-conv">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
          <span>暂无对话</span>
        </div>
      </div>
    </div>

    <div class="sidebar-footer">
      <div class="conv-count">{{ chatStore.conversationsByMode(currentMode).value.length }} 个对话</div>
      <el-dropdown trigger="click">
        <button class="settings-btn" title="设置">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="8" cy="8" r="2.5"/>
            <path d="M13.5 8a5.5 5.5 0 01-.3 1.8l1.2.7-.8 1.4-1.2-.5a5.5 5.5 0 01-1.5 1l.2 1.3h-1.6l.2-1.3a5.5 5.5 0 01-1.5-1l-1.2.5-.8-1.4 1.2-.7A5.5 5.5 0 016 8a5.5 5.5 0 01.3-1.8l-1.2-.7.8-1.4 1.2.5a5.5 5.5 0 011.5-1L8.4 2.3h1.6l-.2 1.3a5.5 5.5 0 011.5 1l1.2-.5.8 1.4-1.2.7c.2.6.3 1.2.3 1.8z"/>
          </svg>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="authStore.logout(); router.push('/login')">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </aside>
</template>

<style scoped>
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

/* ── Mode Switcher ────────────────────────────────────── */
.mode-switcher {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.mode-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--space-2) var(--space-1);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: none;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  font-family: var(--font-body);
}

.mode-btn:hover {
  border-color: var(--color-border-hover);
  background: var(--color-muted);
}

.mode-btn.active {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.mode-icon {
  font-size: 16px;
}

.mode-label {
  font-size: 11px;
  font-weight: var(--font-medium);
  color: var(--color-secondary);
}

.mode-btn.active .mode-label {
  color: var(--color-accent);
}

.sidebar-divider {
  height: 1px;
  background: var(--color-border);
  margin-bottom: var(--space-4);
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  height: 40px;
  background: var(--color-foreground);
  color: white;
  border: none;
  border-radius: var(--radius);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  font-family: var(--font-body);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  margin-bottom: var(--space-4);
}

.new-chat-btn:hover {
  background: var(--color-primary);
  transform: translateY(-1px);
  box-shadow: var(--shadow);
}

.conv-section-label {
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

/* ── Footer ───────────────────────────────────────────── */
.sidebar-footer {
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.conv-count {
  font-size: var(--text-xs);
  color: var(--color-secondary);
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
