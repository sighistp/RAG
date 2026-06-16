<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

interface KnowledgeBase {
  kb_id: string
  name: string
  doc_count: number
}

const knowledgeBases = ref<KnowledgeBase[]>([])
const loading = ref(false)

onMounted(async () => {
  await loadKBs()
})

async function loadKBs() {
  loading.value = true
  try {
    const res = await axios.get('/knowledge-bases', {
      headers: authStore.getAuthHeaders()
    })
    knowledgeBases.value = res.data
  } catch {
    // Ignore
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="kb-page">
    <div class="kb-grid">
      <div
        v-for="kb in knowledgeBases"
        :key="kb.kb_id"
        class="kb-card"
      >
        <div class="kb-header">
          <div class="kb-icon">
            <el-icon><Collection /></el-icon>
          </div>
          <div>
            <div class="kb-name">{{ kb.name }}</div>
            <div class="kb-count">{{ kb.doc_count }} 个文档</div>
          </div>
        </div>
        <div class="kb-stats">
          <div class="stat">
            <div class="stat-value">{{ kb.doc_count }}</div>
            <div class="stat-label">文档</div>
          </div>
        </div>
      </div>

      <div v-if="!knowledgeBases.length && !loading" class="empty-state">
        <el-icon class="empty-icon"><Collection /></el-icon>
        <h3>暂无知识库</h3>
        <p>通过 API 创建知识库</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kb-page {
  padding: var(--space-6);
  overflow-y: auto;
  height: 100%;
}

.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-5);
}

.kb-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  transition: all var(--duration-normal) var(--ease-out);
}

.kb-card:hover {
  box-shadow: var(--shadow-md);
}

.kb-header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.kb-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, var(--color-accent), var(--color-accent-hover));
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
}

.kb-name {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
}

.kb-count {
  font-size: var(--text-sm);
  color: var(--color-secondary);
}

.kb-stats {
  display: flex;
  gap: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.stat {
  text-align: center;
  flex: 1;
}

.stat-value {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  font-family: var(--font-mono);
  color: var(--color-accent);
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--color-secondary);
  margin-top: var(--space-1);
}

.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-16);
  color: var(--color-secondary);
}

.empty-icon {
  font-size: 64px;
  color: var(--color-border);
}
</style>
