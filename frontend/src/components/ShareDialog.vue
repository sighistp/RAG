<template>
  <el-dialog v-model="visible" title="文档共享管理" width="480px">
    <div class="share-section">
      <h4>当前权限等级</h4>
      <el-select v-model="localLevel" @change="updateLevel" style="width: 100%;">
        <el-option :value="1" label="1 - 普通员工" />
        <el-option :value="2" label="2 - 组长" />
        <el-option :value="3" label="3 - 主管" />
        <el-option :value="4" label="4 - 总监" />
        <el-option :value="5" label="5 - 管理员" />
      </el-select>
    </div>

    <div class="share-section" style="margin-top: 20px;">
      <h4>已共享用户</h4>
      <div v-if="sharedUsers.length === 0" class="empty-hint">暂无共享用户</div>
      <div v-for="u in sharedUsers" :key="u.id" class="shared-user-row">
        <span>{{ u.username }}</span>
        <el-button size="small" type="danger" text @click="unshare(u.id)">撤销</el-button>
      </div>
    </div>

    <div class="share-section" style="margin-top: 20px;">
      <h4>添加共享</h4>
      <div style="display: flex; gap: 8px;">
        <el-input v-model="newUserId" placeholder="用户 ID" type="number" />
        <el-button type="primary" @click="share">共享</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import api from '../utils/api'

const props = defineProps<{ docId: number | null }>()
const visible = defineModel<boolean>('visible')
const localLevel = ref(1)
const sharedUsers = ref<any[]>([])
const newUserId = ref('')

watch(visible, async (v) => {
  if (v && props.docId) {
    await loadPermissions()
  }
})

async function loadPermissions() {
  const resp = await api.get(`/documents/${props.docId}/permissions`)
  localLevel.value = resp.data.permission_level
  sharedUsers.value = resp.data.shared_with || []
}

async function updateLevel() {
  await api.put(`/documents/${props.docId}/permission`, { permission_level: localLevel.value })
}

async function share() {
  if (!newUserId.value) return
  try {
    await api.post(`/documents/${props.docId}/share`, { user_id: Number(newUserId.value) })
    newUserId.value = ''
    await loadPermissions()
  } catch (e: any) {
    // 错误已由 api interceptor 处理
  }
}

async function unshare(userId: number) {
  await api.delete(`/documents/${props.docId}/share/${userId}`)
  await loadPermissions()
}
</script>

<style scoped>
.share-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--color-text-secondary);
}
.shared-user-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border);
}
.empty-hint {
  color: var(--color-text-tertiary);
  font-size: 13px;
}
</style>
