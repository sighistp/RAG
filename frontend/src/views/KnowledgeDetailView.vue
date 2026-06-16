<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const kbId = route.params.id as string
const kbName = ref('')
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await axios.get('/knowledge-bases', {
      headers: authStore.getAuthHeaders()
    })
    const kb = res.data.find((k: any) => k.kb_id === kbId)
    if (kb) {
      kbName.value = kb.name
    } else {
      ElMessage.error('知识库不存在')
      router.push('/knowledge')
    }
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
})

function goBack() {
  router.push('/knowledge')
}
</script>

<template>
  <div class="kb-detail-page">
    <div class="kb-detail-header">
      <el-button text @click="goBack">
        <el-icon style="margin-right: 4px;"><ArrowLeft /></el-icon>
        返回列表
      </el-button>
      <h1 v-if="!loading" class="kb-detail-title">{{ kbName }}</h1>
      <div v-else class="skeleton-line skeleton-line--title" style="width: 200px; height: 28px; margin-top: 8px;"></div>
    </div>

    <div class="kb-detail-body">
      <div class="kb-detail-empty">
        <p style="color: var(--color-secondary);">知识库文档管理功能即将推出</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kb-detail-page {
  padding: var(--space-6) var(--space-8);
  height: 100%;
  overflow-y: auto;
}

.kb-detail-header {
  margin-bottom: var(--space-8);
}

.kb-detail-title {
  font-family: var(--font-heading);
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-foreground);
  margin-top: var(--space-4);
}

.kb-detail-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.kb-detail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-16) var(--space-8);
  text-align: center;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.skeleton-line {
  border-radius: var(--radius-sm);
  background: var(--color-muted);
  animation: shimmer 1.5s infinite;
  background-size: 200% 100%;
  background-image: linear-gradient(90deg, var(--color-muted) 25%, var(--color-border) 50%, var(--color-muted) 75%);
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
</style>
