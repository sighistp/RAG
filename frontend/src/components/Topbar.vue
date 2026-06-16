<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useChatStore } from '../stores/chat'

const router = useRouter()
const route = useRoute()
const chatStore = useChatStore()

const activePage = computed(() => {
  if (route.name === 'files') return 'files'
  if (route.name === 'knowledge') return 'knowledge'
  if (route.name === 'analytics') return 'analytics'
  return 'chat'
})

const navItems = [
  { key: 'chat', label: '对话' },
  { key: 'files', label: '文件' },
  { key: 'knowledge', label: '知识库' },
  { key: 'analytics', label: '分析' }
]

function switchPage(page: string) {
  router.push(page === 'chat' ? '/' : `/${page}`)
}
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <h1 class="page-title">{{ chatStore.currentConversation?.title || '新对话' }}</h1>
    </div>
    <nav class="topbar-nav">
      <button
        v-for="item in navItems"
        :key="item.key"
        :class="['nav-item', { active: activePage === item.key }]"
        @click="switchPage(item.key)"
      >
        {{ item.label }}
      </button>
    </nav>
  </header>
</template>

<style scoped>
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
</style>
