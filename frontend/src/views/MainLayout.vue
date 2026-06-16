<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import Sidebar from '../components/Sidebar.vue'

const chatStore = useChatStore()

onMounted(async () => {
  await chatStore.loadConversations()
})
</script>

<template>
  <div class="layout">
    <Sidebar />

    <main class="main">
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

/* ── Main ─────────────────────────────────────────────── */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ── Page Content ─────────────────────────────────────── */
.page-content {
  flex: 1;
  overflow: hidden;
}
</style>
