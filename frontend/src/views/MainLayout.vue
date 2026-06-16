<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { useFilesStore } from '../stores/files'
import Sidebar from '../components/Sidebar.vue'
import Topbar from '../components/Topbar.vue'

const chatStore = useChatStore()
const filesStore = useFilesStore()

onMounted(async () => {
  await Promise.all([
    chatStore.loadConversations(),
    filesStore.loadFiles()
  ])
})
</script>

<template>
  <div class="layout">
    <Sidebar />

    <!-- Main -->
    <main class="main">
      <Topbar />

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
