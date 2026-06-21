<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../utils/api'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import { useAnalysis } from '../composables/useAnalysis'
import MessageBubble from '../components/MessageBubble.vue'
import ChatInput from '../components/ChatInput.vue'
import AddToAnalysisDialog from '../components/AddToAnalysisDialog.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  ArrowUp,
  ArrowDown,
  Edit,
  Check,
  Close,
  Delete,
  Plus,
  ChatDotRound,
  Collection,
  Setting,
  Document,
  Upload,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const chatStore = useChatStore()
const { addToAnalysis, dialogVisible, dialogQuestion, dialogAnswer, handleConfirm } = useAnalysis()

const kbId = route.params.id as string
const loading = ref(true)
const messagesContainer = ref<HTMLElement>()

// KB detail data
const kbName = ref('')
const kbDescription = ref('')
const kbOverview = ref('')
const documents = ref<any[]>([])

// Overview editing
const editingOverview = ref(false)
const overviewDraft = ref('')
const savingOverview = ref(false)

// Settings menu
const showSettingsMenu = ref(false)

// Rename KB
const showRenameDialog = ref(false)
const renameDraft = ref('')
const renaming = ref(false)

// Add files dialog
const showAddDialog = ref(false)
const availableFiles = ref<any[]>([])
const loadingFiles = ref(false)
const selectedFile = ref<any>(null)
const addingFile = ref(false)

// Remove / delete states
const removingDoc = ref('')

// TOC / Overview generation
const generatingToc = ref(false)
const generatingOverview = ref(false)

// Collapsible top section
const showTopSection = ref(true)

// ── Scroll handling ──
watch(() => chatStore.messages.length, () => {
  nextTick(() => { messagesContainer.value?.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' }) })
})

watch(() => chatStore.messages[chatStore.messages.length - 1]?.content, () => {
  nextTick(() => { messagesContainer.value?.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' }) })
})

onMounted(async () => {
  // Load KB conversations and auto-create only if no current KB conversation
  await chatStore.loadConversations('kb')
  const hasKbConv = chatStore.conversations.some(c => c.id === chatStore.currentConvId)
  if (!hasKbConv) {
    await chatStore.createConversation('kb')
  }
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
      router.push('/kb')
      return
    }
    ElMessage.error('加载知识库详情失败')
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push('/kb')
}

// ── Conversation management ──
async function newConversation() {
  await chatStore.createConversation('kb')
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

function askSuggested(q: string) {
  chatStore.sendMessage(q)
}

// ── Settings menu actions ──
function openRenameDialog() {
  renameDraft.value = kbName.value
  showRenameDialog.value = true
  showSettingsMenu.value = false
}

async function renameKB() {
  const name = renameDraft.value.trim()
  if (!name) return ElMessage.warning('请输入名称')
  renaming.value = true
  try {
    await api.put(`/knowledge-bases/${kbId}/name`, { name }, {
      headers: authStore.getAuthHeaders()
    })
    kbName.value = name
    showRenameDialog.value = false
    ElMessage.success('已重命名')
  } catch {
    ElMessage.error('重命名失败')
  } finally {
    renaming.value = false
  }
}

async function generateTOC() {
  showSettingsMenu.value = false
  generatingToc.value = true
  try {
    const res = await api.post(`/knowledge-bases/${kbId}/toc/generate`, {}, {
      headers: authStore.getAuthHeaders()
    })
    // Update local document state with generated TOC
    const tocData = res.data.toc || {}
    for (const doc of documents.value) {
      if (tocData[doc.filename]) {
        doc.toc = JSON.stringify(tocData[doc.filename])
      }
    }
    ElMessage.success('目录生成完成')
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '目录生成失败')
  } finally {
    generatingToc.value = false
  }
}

async function generateOverview() {
  showSettingsMenu.value = false
  generatingOverview.value = true
  try {
    const res = await api.post(`/knowledge-bases/${kbId}/overview/generate`, {}, {
      headers: authStore.getAuthHeaders()
    })
    kbOverview.value = res.data.overview || ''
    ElMessage.success('概述生成完成')
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '概述生成失败')
  } finally {
    generatingOverview.value = false
  }
}

async function deleteKB() {
  showSettingsMenu.value = false
  try {
    await ElMessageBox.confirm(
      `确定删除知识库「${kbName.value}」吗？此操作不可恢复。`,
      '删除知识库',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'error' }
    )
    await api.delete(`/knowledge-bases/${kbId}`, {
      headers: authStore.getAuthHeaders()
    })
    ElMessage.success('知识库已删除')
    router.push('/kb')
  } catch (err: any) {
    if (err !== 'cancel' && err?.message !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
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
  showSettingsMenu.value = false
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
    const formData = new FormData()
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
  <div class="kb-detail-layout">
    <!-- Conversation sidebar -->
    <aside class="conv-sidebar">
      <div class="conv-sidebar-header">
        <span class="conv-sidebar-title">对话历史</span>
        <button class="new-chat-btn" @click="newConversation">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="8" y1="2" x2="8" y2="14"/>
            <line x1="2" y1="8" x2="14" y2="8"/>
          </svg>
          新建
        </button>
      </div>

      <div class="conv-list">
        <div
          v-for="conv in chatStore.conversations"
          :key="conv.id"
          :class="['conv-item', { active: conv.id === chatStore.currentConvId }]"
          @click="selectConversation(conv.id)"
        >
          <div class="conv-icon">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M2 3h12v8H4l-2 2V3z"/>
            </svg>
          </div>
          <div class="conv-info">
            <div class="conv-title">{{ conv.title || '新对话' }}</div>
            <div class="conv-time">{{ formatTime(conv.created_at) }}</div>
          </div>
          <button class="conv-delete" @click.stop="deleteConversation(conv.id)" title="删除">
            <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
              <line x1="3" y1="3" x2="11" y2="11"/>
              <line x1="11" y1="3" x2="3" y2="11"/>
            </svg>
          </button>
        </div>

        <div v-if="!chatStore.conversations.length" class="empty-conv">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
          <span>暂无对话</span>
        </div>
      </div>

      <div class="conv-sidebar-footer">
        {{ chatStore.conversations.length }} 个对话
      </div>
    </aside>

    <!-- Main content area -->
    <div class="kb-detail-main">
      <!-- Header -->
      <div class="kb-detail-header">
        <div class="kb-detail-header-top">
          <el-button text @click="goBack">
            <el-icon style="margin-right: 4px;"><ArrowLeft /></el-icon>
            返回列表
          </el-button>
          <el-button text size="small" @click="showTopSection = !showTopSection" :title="showTopSection ? '收起信息区' : '展开信息区'">
            <el-icon style="margin-right: 4px;"><ArrowUp v-if="showTopSection" /><ArrowDown v-else /></el-icon>
            {{ showTopSection ? '收起' : '展开' }}
          </el-button>
        </div>
        <div class="kb-detail-header-row">
          <div v-if="!loading" class="kb-detail-title-area">
            <el-icon class="kb-detail-title-icon"><Collection /></el-icon>
            <h1 class="kb-detail-title">{{ kbName }}</h1>
            <!-- Settings menu -->
            <el-dropdown trigger="click" v-model:visible="showSettingsMenu">
              <el-button text size="small" class="settings-btn">
                <el-icon><Setting /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="openRenameDialog">
                    <el-icon style="margin-right: 6px;"><Edit /></el-icon>
                    编辑名称
                  </el-dropdown-item>
                  <el-dropdown-item @click="generateTOC" :loading="generatingToc" :disabled="generatingToc">
                    <el-icon style="margin-right: 6px;"><Document /></el-icon>
                    {{ generatingToc ? '生成中...' : '生成目录' }}
                  </el-dropdown-item>
                  <el-dropdown-item @click="generateOverview" :loading="generatingOverview" :disabled="generatingOverview">
                    <el-icon style="margin-right: 6px;"><Document /></el-icon>
                    {{ generatingOverview ? '生成中...' : '生成概述' }}
                  </el-dropdown-item>
                  <el-dropdown-item @click="openAddDialog">
                    <el-icon style="margin-right: 6px;"><Upload /></el-icon>
                    添加内容
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="deleteKB" class="danger-item">
                    <el-icon style="margin-right: 6px;"><Delete /></el-icon>
                    删除知识库
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <div v-else class="skeleton-line skeleton-line--title" style="width: 200px; height: 28px;"></div>
          <el-button type="primary" @click="chatStore.createConversation('kb')" :disabled="loading">
            <el-icon style="margin-right: 6px;"><ChatDotRound /></el-icon>
            新对话
          </el-button>
        </div>
      </div>

      <!-- Scrollable content (collapsible) -->
      <div v-if="showTopSection" class="kb-detail-scroll">
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
      </div>

      <!-- Chat area (fixed at bottom) -->
      <div class="kb-detail-chat">
        <div ref="messagesContainer" class="messages">
          <div v-if="!chatStore.messages.length" class="empty-chat">
            <el-icon :size="32" style="color: var(--color-border);"><ChatDotRound /></el-icon>
            <p>在此知识库中提问</p>
          </div>

          <MessageBubble
            v-for="(msg, i) in chatStore.messages"
            :key="i"
            :message="msg"
            :index="i"
            :question="i > 0 && chatStore.messages[i - 1]?.role === 'user' ? chatStore.messages[i - 1].content : ''"
            @add-to-analysis="addToAnalysis"
          />

          <div v-if="chatStore.isStreaming && !chatStore.messages[chatStore.messages.length - 1]?.content" class="msg assistant">
            <div class="msg-avatar ai-avatar">R</div>
            <div class="msg-body">
              <div class="typing"><span></span><span></span><span></span></div>
            </div>
          </div>
        </div>

        <div v-if="chatStore.suggestedQuestions.length" class="suggestions">
          <button v-for="q in chatStore.suggestedQuestions" :key="q" class="suggest-btn" @click="askSuggested(q)">
            {{ q }}
          </button>
        </div>

        <ChatInput />
      </div>
    </div>

    <!-- Rename dialog -->
    <el-dialog v-model="showRenameDialog" title="重命名知识库" width="420px" :close-on-click-modal="false">
      <el-input v-model="renameDraft" placeholder="输入知识库名称" maxlength="100" @keyup.enter="renameKB" />
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" :loading="renaming" @click="renameKB">保存</el-button>
      </template>
    </el-dialog>

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

    <AddToAnalysisDialog
      v-model:visible="dialogVisible"
      :question="dialogQuestion"
      :answer="dialogAnswer"
      @confirm="handleConfirm"
    />
  </div>
</template>

<style scoped>
.kb-detail-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* ── Conversation Sidebar ─────────────────────────────── */
.conv-sidebar {
  width: 240px;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.conv-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.conv-sidebar-title {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  background: var(--color-foreground);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  font-family: var(--font-body);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.new-chat-btn:hover {
  background: var(--color-primary);
  transform: translateY(-1px);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
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
  width: 28px;
  height: 28px;
  background: var(--color-muted);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-secondary);
  flex-shrink: 0;
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
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--color-foreground);
}

.conv-time {
  font-size: 10px;
  color: var(--color-secondary);
  margin-top: 1px;
}

.conv-delete {
  opacity: 0;
  width: 24px;
  height: 24px;
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
  font-size: var(--text-xs);
}

.conv-sidebar-footer {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border);
  font-size: 11px;
  color: var(--color-secondary);
}

/* ── Main Content ──────────────────────────────────────── */
.kb-detail-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-background);
}

/* ── Header ── */
.kb-detail-header {
  padding: var(--space-4) var(--space-6);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
  flex-shrink: 0;
}

.kb-detail-header-top {
  margin-bottom: var(--space-2);
  display: flex;
  align-items: center;
  justify-content: space-between;
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
  font-size: 24px;
  color: var(--color-accent);
}

.kb-detail-title {
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--color-foreground);
  margin: 0;
}

.settings-btn {
  font-size: 18px;
  color: var(--color-secondary);
}

.settings-btn:hover {
  color: var(--color-foreground);
}

/* ── Scrollable content ── */
.kb-detail-scroll {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5) var(--space-6);
}

/* ── Section ── */
.kb-section {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
}

.kb-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.kb-section-title {
  font-family: var(--font-heading);
  font-size: var(--text-base);
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
  padding: var(--space-3);
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
  margin-left: var(--space-3);
}

.kb-docs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-6) var(--space-4);
  color: var(--color-secondary);
  font-size: var(--text-sm);
}

/* ── Chat area ── */
.kb-detail-chat {
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 200px;
  overflow: hidden;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) 0;
}

.empty-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--color-secondary);
  gap: var(--space-2);
}

.empty-chat p {
  font-size: var(--text-sm);
  margin: 0;
}

.msg {
  display: flex;
  gap: var(--space-4);
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-3) var(--space-6);
  animation: slideUp 0.3s var(--ease-out);
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: var(--font-bold);
}

.ai-avatar {
  background: var(--color-foreground);
  color: white;
  font-family: var(--font-mono);
  font-size: 12px;
}

.msg-body {
  flex: 1;
  min-width: 0;
  max-width: 85%;
}

.typing {
  display: flex;
  gap: 6px;
  padding: var(--space-4);
}

.typing span {
  width: 8px;
  height: 8px;
  background: var(--color-border);
  border-radius: 50%;
  animation: bounce 1.4s infinite;
}

.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-8px); }
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: 0 var(--space-6) var(--space-3);
}

.suggest-btn {
  padding: var(--space-1) var(--space-3);
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  color: var(--color-secondary);
  cursor: pointer;
  font-family: var(--font-body);
  transition: all var(--duration-normal) var(--ease-out);
}

.suggest-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
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

/* ── Danger item in dropdown ── */
.danger-item {
  color: var(--color-destructive) !important;
}

.danger-item:hover {
  background: var(--color-destructive-light) !important;
}

/* ── Skeleton ── */
.skeleton-line {
  border-radius: var(--radius-sm);
  background: var(--color-muted);
  animation: shimmer 1.5s infinite;
  background-size: 200% 100%;
  background-image: linear-gradient(90deg, var(--color-muted) 25%, var(--color-border) 50%, var(--color-muted) 75%);
}

.skeleton-line--title {
  width: 60%;
  height: 16px;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
