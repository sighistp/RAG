<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../utils/api'
import { useAuthStore } from '../stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Edit,
  Check,
  Close,
  Delete,
  Plus,
  ChatDotRound,
  Collection,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const kbId = route.params.id as string
const loading = ref(true)

// KB detail data
const kbName = ref('')
const kbDescription = ref('')
const kbOverview = ref('')
const documents = ref<any[]>([])

// Overview editing
const editingOverview = ref(false)
const overviewDraft = ref('')
const savingOverview = ref(false)

// Add files dialog
const showAddDialog = ref(false)
const availableFiles = ref<any[]>([])
const loadingFiles = ref(false)
const selectedFile = ref<any>(null)
const addingFile = ref(false)

// Remove / delete states
const removingDoc = ref('')

onMounted(async () => {
  await loadDetail()
})

async function loadDetail() {
  loading.value = true
  try {
    const res = await api.get(`/knowledge-bases/${kbId}`, {
      headers: authStore.getAuthHeaders()
    })
    const data = res.data
    kbName.value = data.name || ''
    kbDescription.value = data.description || ''
    kbOverview.value = data.overview || ''
    documents.value = data.documents || []
  } catch (err: any) {
    if (err.response?.status === 404) {
      ElMessage.error('知识库不存在')
      router.push('/knowledge')
      return
    }
    ElMessage.error('加载知识库详情失败')
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push('/knowledge')
}

function goToAsk() {
  router.push({ path: '/', query: { kb_id: kbId } })
}

// ── Overview editing ──
function startEditOverview() {
  overviewDraft.value = kbOverview.value
  editingOverview.value = true
}

function cancelEditOverview() {
  editingOverview.value = false
  overviewDraft.value = ''
}

async function saveOverview() {
  savingOverview.value = true
  try {
    await api.put(`/knowledge-bases/${kbId}/overview`, { overview: overviewDraft.value }, {
      headers: authStore.getAuthHeaders()
    })
    kbOverview.value = overviewDraft.value
    editingOverview.value = false
    ElMessage.success('概述已更新')
  } catch {
    ElMessage.error('保存概述失败')
  } finally {
    savingOverview.value = false
  }
}

// ── Document management ──
async function removeFromKB(doc: any) {
  try {
    await ElMessageBox.confirm(
      `确定将「${doc.filename}」从知识库移除？`,
      '从知识库移除',
      { confirmButtonText: '移除', cancelButtonText: '取消', type: 'warning' }
    )
    removingDoc.value = doc.filename
    await api.delete(`/knowledge-bases/${kbId}/documents/${encodeURIComponent(doc.filename)}`, {
      headers: authStore.getAuthHeaders()
    })
    ElMessage.success('已从知识库移除')
    await loadDetail()
  } catch (err: any) {
    if (err !== 'cancel' && err?.message !== 'cancel') {
      ElMessage.error('移除失败')
    }
  } finally {
    removingDoc.value = ''
  }
}

async function deleteFile(doc: any) {
  try {
    await ElMessageBox.confirm(
      `确定永久删除文件「${doc.filename}」？此操作不可恢复。`,
      '删除文件',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'error' }
    )
    removingDoc.value = doc.filename
    await api.delete(`/files/${encodeURIComponent(doc.filename)}`, {
      headers: authStore.getAuthHeaders()
    })
    ElMessage.success('文件已删除')
    await loadDetail()
  } catch (err: any) {
    if (err !== 'cancel' && err?.message !== 'cancel') {
      ElMessage.error('删除失败')
    }
  } finally {
    removingDoc.value = ''
  }
}

// ── Add files to KB ──
async function openAddDialog() {
  showAddDialog.value = true
  selectedFile.value = null
  await loadAvailableFiles()
}

async function loadAvailableFiles() {
  loadingFiles.value = true
  try {
    const res = await api.get('/files', {
      headers: authStore.getAuthHeaders()
    })
    // Filter out files already in this KB
    const kbFileNames = new Set(documents.value.map(d => d.filename))
    availableFiles.value = (res.data.files || []).filter(
      (f: any) => !f.in_kb && !kbFileNames.has(f.name)
    )
  } catch {
    ElMessage.error('加载文件列表失败')
  } finally {
    loadingFiles.value = false
  }
}

async function addFileToKB() {
  if (!selectedFile.value) return
  addingFile.value = true
  try {
    // Read the file from data/upload directory and upload as FormData
    const formData = new FormData()
    // We need to fetch the actual file content. Use the upload endpoint approach.
    // Since the file is on disk, we construct a FormData and send it.
    // The API expects a file upload, so we'll use a Blob approach.
    const res = await fetch(`/data/upload/${encodeURIComponent(selectedFile.value.name)}`)
    if (!res.ok) throw new Error('无法读取文件')
    const blob = await res.blob()
    formData.append('file', blob, selectedFile.value.name)

    await api.post(`/knowledge-bases/${kbId}/documents`, formData, {
      headers: authStore.getAuthHeaders()
    })
    ElMessage.success('文件已添加到知识库')
    showAddDialog.value = false
    await loadDetail()
  } catch {
    ElMessage.error('添加文件失败')
  } finally {
    addingFile.value = false
  }
}

function getStatusType(status: string) {
  switch (status) {
    case 'indexed': return 'success'
    case 'pending': return 'warning'
    case 'error': return 'danger'
    default: return 'info'
  }
}

function getStatusLabel(status: string) {
  switch (status) {
    case 'indexed': return '已索引'
    case 'pending': return '处理中'
    case 'error': return '错误'
    default: return status || '未知'
  }
}
</script>

<template>
  <div class="kb-detail-page">
    <!-- Header -->
    <div class="kb-detail-header">
      <div class="kb-detail-header-top">
        <el-button text @click="goBack">
          <el-icon style="margin-right: 4px;"><ArrowLeft /></el-icon>
          返回列表
        </el-button>
      </div>
      <div class="kb-detail-header-row">
        <div v-if="!loading" class="kb-detail-title-area">
          <el-icon class="kb-detail-title-icon"><Collection /></el-icon>
          <h1 class="kb-detail-title">{{ kbName }}</h1>
        </div>
        <div v-else class="skeleton-line skeleton-line--title" style="width: 200px; height: 28px;"></div>
        <el-button type="primary" @click="goToAsk" :disabled="loading">
          <el-icon style="margin-right: 6px;"><ChatDotRound /></el-icon>
          在此知识库中提问
        </el-button>
      </div>
    </div>

    <!-- Overview section -->
    <div class="kb-section">
      <div class="kb-section-header">
        <h2 class="kb-section-title">知识库概述</h2>
        <el-button
          v-if="!editingOverview"
          text
          size="small"
          @click="startEditOverview"
        >
          <el-icon style="margin-right: 4px;"><Edit /></el-icon>
          编辑概述
        </el-button>
      </div>
      <div v-if="loading" class="skeleton-line" style="width: 100%; height: 60px;"></div>
      <div v-else-if="editingOverview" class="kb-overview-edit">
        <el-input
          v-model="overviewDraft"
          type="textarea"
          :rows="4"
          placeholder="输入知识库概述..."
        />
        <div class="kb-overview-edit-actions">
          <el-button size="small" @click="cancelEditOverview">
            <el-icon style="margin-right: 4px;"><Close /></el-icon>
            取消
          </el-button>
          <el-button type="primary" size="small" :loading="savingOverview" @click="saveOverview">
            <el-icon style="margin-right: 4px;"><Check /></el-icon>
            保存
          </el-button>
        </div>
      </div>
      <div v-else class="kb-overview-display">
        <p v-if="kbOverview" class="kb-overview-text">{{ kbOverview }}</p>
        <p v-else class="kb-overview-empty">暂无概述，点击「编辑概述」添加</p>
      </div>
    </div>

    <!-- Documents section -->
    <div class="kb-section">
      <div class="kb-section-header">
        <h2 class="kb-section-title">文档列表</h2>
        <el-button type="primary" size="small" @click="openAddDialog">
          <el-icon style="margin-right: 4px;"><Plus /></el-icon>
          添加文件
        </el-button>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="kb-docs-list">
        <div v-for="i in 3" :key="i" class="kb-doc-card kb-doc-card--skeleton">
          <div class="skeleton-line" style="width: 40%; height: 16px;"></div>
          <div class="skeleton-line" style="width: 25%; height: 12px;"></div>
        </div>
      </div>

      <!-- Empty -->
      <div v-else-if="documents.length === 0" class="kb-docs-empty">
        <p>知识库中暂无文档</p>
        <el-button type="primary" size="small" @click="openAddDialog">
          <el-icon style="margin-right: 4px;"><Plus /></el-icon>
          添加文件
        </el-button>
      </div>

      <!-- Document list -->
      <div v-else class="kb-docs-list">
        <div
          v-for="doc in documents"
          :key="doc.filename"
          class="kb-doc-card"
        >
          <div class="kb-doc-info">
            <div class="kb-doc-name">{{ doc.filename }}</div>
            <div class="kb-doc-meta">
              <span class="kb-doc-chunks">{{ doc.chunk_count }} 个分块</span>
              <el-tag
                v-if="doc.status"
                :type="getStatusType(doc.status)"
                size="small"
                effect="plain"
              >
                {{ getStatusLabel(doc.status) }}
              </el-tag>
            </div>
            <div v-if="doc.summary" class="kb-doc-summary">{{ doc.summary }}</div>
          </div>
          <div class="kb-doc-actions">
            <el-button
              text
              size="small"
              :loading="removingDoc === doc.filename"
              @click="removeFromKB(doc)"
            >
              从知识库移除
            </el-button>
            <el-button
              type="danger"
              text
              size="small"
              :loading="removingDoc === doc.filename"
              @click="deleteFile(doc)"
            >
              <el-icon style="margin-right: 2px;"><Delete /></el-icon>
              删除文件
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add file dialog -->
    <el-dialog
      v-model="showAddDialog"
      title="添加文件到知识库"
      width="520px"
      :close-on-click-modal="false"
    >
      <div v-if="loadingFiles" class="kb-add-loading">
        <p>加载文件列表...</p>
      </div>
      <div v-else-if="availableFiles.length === 0" class="kb-add-empty">
        <p>暂无可添加的文件</p>
        <p class="kb-add-hint">请先在「文件管理」页面上传文件</p>
      </div>
      <div v-else class="kb-add-list">
        <div
          v-for="file in availableFiles"
          :key="file.name"
          class="kb-add-item"
          :class="{ 'kb-add-item--selected': selectedFile?.name === file.name }"
          @click="selectedFile = file"
        >
          <div class="kb-add-item-info">
            <div class="kb-add-item-name">{{ file.name }}</div>
            <div class="kb-add-item-meta">{{ file.size_human }}</div>
          </div>
          <div
            v-if="selectedFile?.name === file.name"
            class="kb-add-item-check"
          >
            <el-icon><Check /></el-icon>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="addingFile"
          :disabled="!selectedFile"
          @click="addFileToKB"
        >
          添加
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.kb-detail-page {
  padding: var(--space-6) var(--space-8);
  height: 100%;
  overflow-y: auto;
}

/* ── Header ── */
.kb-detail-header {
  margin-bottom: var(--space-8);
}

.kb-detail-header-top {
  margin-bottom: var(--space-2);
}

.kb-detail-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kb-detail-title-area {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.kb-detail-title-icon {
  font-size: 28px;
  color: var(--color-accent);
}

.kb-detail-title {
  font-family: var(--font-heading);
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-foreground);
  margin: 0;
}

/* ── Section ── */
.kb-section {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  margin-bottom: var(--space-5);
}

.kb-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.kb-section-title {
  font-family: var(--font-heading);
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
  margin: 0;
}

/* ── Overview ── */
.kb-overview-display {
  min-height: 40px;
}

.kb-overview-text {
  font-size: var(--text-sm);
  color: var(--color-secondary);
  line-height: var(--leading-relaxed);
  white-space: pre-wrap;
  margin: 0;
}

.kb-overview-empty {
  font-size: var(--text-sm);
  color: var(--color-muted);
  font-style: italic;
  margin: 0;
}

.kb-overview-edit {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.kb-overview-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

/* ── Documents list ── */
.kb-docs-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.kb-doc-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  transition: border-color var(--duration-normal) var(--ease-out);
}

.kb-doc-card:hover {
  border-color: var(--color-accent);
}

.kb-doc-card--skeleton {
  cursor: default;
  pointer-events: none;
}

.kb-doc-info {
  flex: 1;
  min-width: 0;
}

.kb-doc-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-foreground);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kb-doc-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
}

.kb-doc-chunks {
  font-size: var(--text-xs);
  color: var(--color-secondary);
}

.kb-doc-summary {
  font-size: var(--text-xs);
  color: var(--color-muted);
  margin-top: var(--space-2);
  line-height: var(--leading-relaxed);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.kb-doc-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
  margin-left: var(--space-4);
}

.kb-docs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-8) var(--space-4);
  color: var(--color-secondary);
  font-size: var(--text-sm);
}

/* ── Add file dialog ── */
.kb-add-loading,
.kb-add-empty {
  text-align: center;
  padding: var(--space-8) var(--space-4);
  color: var(--color-secondary);
  font-size: var(--text-sm);
}

.kb-add-hint {
  font-size: var(--text-xs);
  color: var(--color-muted);
  margin-top: var(--space-2);
}

.kb-add-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: 360px;
  overflow-y: auto;
}

.kb-add-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.kb-add-item:hover {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.kb-add-item--selected {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.kb-add-item-info {
  flex: 1;
  min-width: 0;
}

.kb-add-item-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-foreground);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kb-add-item-meta {
  font-size: var(--text-xs);
  color: var(--color-secondary);
  margin-top: 2px;
}

.kb-add-item-check {
  color: var(--color-accent);
  font-size: 18px;
  flex-shrink: 0;
  margin-left: var(--space-3);
}

/* ── Skeleton ── */
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
