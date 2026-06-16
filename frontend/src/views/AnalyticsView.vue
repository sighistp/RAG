<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../utils/api'

interface GapSummary {
  total: number
  top_questions: Array<{ question: string; count: number }>
}

const summary = ref<GapSummary>({ total: 0, top_questions: [] })
const loading = ref(false)

onMounted(async () => {
  await loadAnalytics()
})

async function loadAnalytics() {
  loading.value = true
  try {
    const res = await api.get('/analytics/gaps/summary')
    summary.value = res.data
  } catch {
    // Ignore
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="analytics-page">
    <!-- Stats cards -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">未解答问题</div>
        <div class="stat-value">{{ summary.total || 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">热门问题</div>
        <div class="stat-value hot-question">
          {{ summary.top_questions?.[0]?.question || '-' }}
        </div>
      </div>
    </div>

    <!-- Gap questions table -->
    <div class="section">
      <h3 class="section-title">未解答问题列表</h3>
      <el-table
        :data="summary.top_questions || []"
        style="width: 100%"
        empty-text="暂无数据"
      >
        <el-table-column prop="question" label="问题" />
        <el-table-column prop="count" label="次数" width="100" />
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.analytics-page {
  padding: var(--space-6);
  overflow-y: auto;
  height: 100%;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-8);
}

.stat-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
}

.stat-label {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wider);
  color: var(--color-secondary);
  margin-bottom: var(--space-3);
}

.stat-value {
  font-size: var(--text-4xl);
  font-weight: var(--font-bold);
  font-family: var(--font-mono);
  color: var(--color-foreground);
}

.hot-question {
  font-size: var(--text-xl);
  font-family: var(--font-body);
  font-weight: var(--font-medium);
}

.section {
  margin-bottom: var(--space-8);
}

.section-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
  margin-bottom: var(--space-4);
}
</style>
