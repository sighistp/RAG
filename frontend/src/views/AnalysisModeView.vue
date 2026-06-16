<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../utils/api'
import { useAuthStore } from '../stores/auth'
import AnalysisCard from '../components/AnalysisCard.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, DataAnalysis } from '@element-plus/icons-vue'

const authStore = useAuthStore()

interface CardGroup {
  id: string
  name: string
  questions: string[]
}

const cards = ref<CardGroup[]>([])
const loading = ref(false)

onMounted(async () => {
  await loadCards()
})

async function loadCards() {
  loading.value = true
  try {
    const res = await api.get('/analysis/cards', { headers: authStore.getAuthHeaders() })
    cards.value = res.data || []
  } catch {
    cards.value = []
  } finally {
    loading.value = false
  }
}

async function createCard() {
  try {
    const res = await api.post('/analysis/cards', { name: '新建卡片组', questions: [] }, { headers: authStore.getAuthHeaders() })
    cards.value.push(res.data)
    ElMessage.success('卡片组已创建')
  } catch {
    ElMessage.error('创建失败')
  }
}

async function updateCardTitle(card: CardGroup, newTitle: string) {
  card.name = newTitle
  try {
    await api.put(`/analysis/cards/${card.id}`, { name: card.name }, { headers: authStore.getAuthHeaders() })
  } catch {
    ElMessage.error('保存失败')
  }
}

async function addQuestion(card: CardGroup, question: string) {
  card.questions.push(question)
  try {
    await api.put(`/analysis/cards/${card.id}`, { questions: card.questions }, { headers: authStore.getAuthHeaders() })
  } catch {
    ElMessage.error('保存失败')
  }
}

async function removeQuestion(card: CardGroup, index: number) {
  card.questions.splice(index, 1)
  try {
    await api.put(`/analysis/cards/${card.id}`, { questions: card.questions }, { headers: authStore.getAuthHeaders() })
  } catch {
    ElMessage.error('保存失败')
  }
}

async function deleteCard(card: CardGroup) {
  try {
    await ElMessageBox.confirm(`确定删除卡片组「${card.name}」吗？`, '删除卡片组', { type: 'warning' })
    await api.delete(`/analysis/cards/${card.id}`, { headers: authStore.getAuthHeaders() })
    cards.value = cards.value.filter(c => c.id !== card.id)
    ElMessage.success('已删除')
  } catch {}
}
</script>

<template>
  <div class="analysis-page">
    <div class="analysis-header">
      <div>
        <h1 class="analysis-title">分析</h1>
        <p class="analysis-subtitle">管理问题卡片组，追踪未解答的问题</p>
      </div>
      <el-button type="primary" @click="createCard">
        <el-icon style="margin-right: 6px;"><Plus /></el-icon>
        新建卡片组
      </el-button>
    </div>

    <div v-if="loading" class="analysis-loading">加载中...</div>

    <div v-else-if="cards.length" class="cards-grid">
      <div v-for="(card, idx) in cards" :key="card.id" class="card-wrapper">
        <AnalysisCard
          :title="card.name"
          :questions="card.questions"
          :index="idx"
          @update:title="(v: string) => updateCardTitle(card, v)"
          @add-question="(q: string) => addQuestion(card, q)"
          @remove-question="(i: number) => removeQuestion(card, i)"
        />
        <button class="card-delete-btn" @click="deleteCard(card)" title="删除卡片组">
          <el-icon><Delete /></el-icon>
        </button>
      </div>
    </div>

    <div v-else class="analysis-empty">
      <div class="analysis-empty-icon">
        <el-icon :size="48"><DataAnalysis /></el-icon>
      </div>
      <h3 class="analysis-empty-title">暂无卡片组</h3>
      <p class="analysis-empty-desc">创建卡片组，组织和追踪问题</p>
      <el-button type="primary" @click="createCard">
        <el-icon style="margin-right: 6px;"><Plus /></el-icon>
        新建卡片组
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.analysis-page {
  padding: var(--space-6) var(--space-8);
  height: 100%;
  overflow-y: auto;
}

.analysis-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-8);
}

.analysis-title {
  font-family: var(--font-heading);
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-foreground);
  margin: 0;
}

.analysis-subtitle {
  font-size: var(--text-sm);
  color: var(--color-secondary);
  margin-top: var(--space-1);
}

.analysis-loading {
  text-align: center;
  color: var(--color-secondary);
  padding: var(--space-16) 0;
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: var(--space-5);
}

.card-wrapper {
  position: relative;
}

.card-delete-btn {
  position: absolute;
  top: var(--space-3);
  right: var(--space-3);
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
  opacity: 0;
  transition: all var(--duration-fast);
}

.card-wrapper:hover .card-delete-btn {
  opacity: 1;
}

.card-delete-btn:hover {
  background: var(--color-destructive-light);
  color: var(--color-destructive);
}

/* ── Empty state ── */
.analysis-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-16) var(--space-8);
}

.analysis-empty-icon {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-xl);
  background: var(--color-accent-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-accent);
  margin-bottom: var(--space-6);
}

.analysis-empty-title {
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
  margin-bottom: var(--space-2);
}

.analysis-empty-desc {
  font-size: var(--text-sm);
  color: var(--color-secondary);
  margin-bottom: var(--space-6);
}
</style>
