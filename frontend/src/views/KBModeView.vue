<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../utils/api'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import MessageBubble from '../components/MessageBubble.vue'
import ChatInput from '../components/ChatInput.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Collection, Document, ArrowLeft, Delete, Upload } from '@element-plus/icons-vue'

const router = useRouter()
const authStore = useAuthStore()
const chatStore = useChatStore()

const messagesContainer = ref<HTMLElement>()

// KB list
interface KnowledgeBase {
  kb_id: string
  name: string
  doc_count: number
}
interface KBDocument {
  filename: string
  chunk_count: number
  status: string
}

const knowledgeBases = ref<KnowledgeBase[]>([])
const loadingKBs = ref(false)
const selectedKBId = ref<string | null>(null)
const kbDocuments = ref<KBDocument[]>([])
const loadingDocs = ref(false)

// Create KB dialog
const showCreateDialog = ref(false)
const newKBName = ref('')
const creating = ref(false)

// Add files to KB dialog
const showAddDialog = ref(false)
const availableFiles = ref<any[]>([])
const loadingFiles = ref(false)
const selectedAddFile = ref<any>(null)
const addingFile = ref(false)

const selectedKB = computed(() => knowledgeBases.value.find(kb => kb.kb_id === selectedKBId.value))

onMounted(async () => {
  await loadKBs()
})

watch(() => chatStore.messages.length, () => {
  nextTick(() => { messagesContainer.value?.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' }) })
})

watch(() => chatStore.messages[chatStore.messages.length - 1]?.content, () => {
  nextTick(() => { messagesContainer.value?.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' }) })
})

function askSuggested(q: string) {
  chatStore.sendMessage(q)
}

// ── KB List ──
async function loadKBs() {
  loadingKBs.value = true
  try {
    const res = await api.get('/knowledge-bases', { headers: authStore.getAuthHeaders() })
    knowledgeBases.value = res.data
  } catch {
    ElMessage.error('加载知识库列表失败')
  } finally {
    loadingKBs.value = false
  }
}

function selectKB(kbId: string) {
  selectedKBId.value = kbId
  loadKBDocuments(kbId)
}

async function loadKBDocuments(kbId: string) {
  loadingDocs.value = true
  try {
    const res = await api.get(`/knowledge-bases/${kbId}`, { headers: authStore.getAuthHeaders() })
    kbDocuments.value = res.data.documents || []
  } catch {
    kbDocuments.value = []
  } finally {
    loadingDocs.value = false
  }
}

function openCreateDialog() {
  newKBName.value = ''
  showCreateDialog.value = true
}

async function createKB() {
  const name = newKBName.value.trim()
  if (!name) return ElMessage.warning('请输入知识库名称')
  creating.value = true
  try {
    await api.post('/knowledge-bases', { name }, { headers: authStore.getAuthHeaders() })
    ElMessage.success('知识库创建成功')
    showCreateDialog.value = false
    await loadKBs()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function deleteKB(kb: KnowledgeBase) {
  try {
    await ElMessageBox.confirm(`确定删除知识库「${kb.name}」吗？`, '删除知识库', { type: 'warning' })
    await api.delete(`/knowledge-bases/${kb.kb_id}`, { headers: authStore.getAuthHeaders() })
    ElMessage.success('已删除')
    if (selectedKBId.value === kb.kb_id) {
      selectedKBId.value = null
      kbDocuments.value = []
    }
    await loadKBs()
  } catch {}
}

// ── Add files to KB ──
async function openAddDialog() {
  showAddDialog.value = true
  selectedAddFile.value = null
  loadingFiles.value = true
  try {
    const res = await api.get('/files', { headers: authStore.getAuthHeaders() })
    const kbFileNames = new Set(kbDocuments.value.map(d => d.filename))
    availableFiles.value = (res.data.files || []).filter((f: any) => !kbFileNames.has(f.name))
  } catch {
    ElMessage.error('加载文件列表失败')
  } finally {
    loadingFiles.value = false
  }
}

async function addFileToKB() {
  if (!selectedAddFile.value || !selectedKBId.value) return
  addingFile.value = true
  try {
    const formData = new FormData()
    const res = await fetch(`/data/upload/${encodeURIComponent(selectedAddFile.value.name)}`)
    if (!res.ok) throw new Error('无法读取文件')
    const blob = await res.blob()
    formData.append('file', blob, selectedAddFile.value.name)
    await api.post(`/knowledge-bases/${selectedKBId.value}/documents`, formData, { headers: authStore.getAuthHeaders() })
    ElMessage.success('文件已添加')
    showAddDialog.value = false
    await loadKBDocuments(selectedKBId.value)
    await loadKBs()
  } catch {
    ElMessage.error('添加文件失败')
  } finally {
    addingFile.value = false
  }
}

async function removeDocument(filename: string) {
  if (!selectedKBId.value) return
  try {
    await api.delete(`/knowledge-bases/${selectedKBId.value}/documents/${encodeURIComponent(filename)}`, { headers: authStore.getAuthHeaders() })
    ElMessage.success('已移除')
    await loadKBDocuments(selectedKBId.value)
    await loadKBs()
  } catch {
    ElMessage.error('移除失败')
  }
}

function goToDetail(kb: KnowledgeBase) {
  router.push(`/knowledge/${kb.kb_id}`)
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
  <div class="kb-mode">
    <!-- Left panel: KB list / documents -->
    <div class="kb-left">
      <div class="kb-left-header">
        <div v-if="!selectedKBId">
          <div class="kb-left-title-row">
            <span class="kb-left-title">知识库</span>
            <el-button size="small" type="primary" @click="openCreateDialog" :icon="Plus" circle />
          </div>
          <div class="kb-list">
            <div v-if="loadingKBs" class="kb-list-loading">加载中...</div>
            <div
              v-for="kb in knowledgeBases"
              :key="kb.kb_id"
              class="kb-list-item"
              @click="selectKB(kb.kb_id)"
            >
              <div class="kb-list-icon"><el-icon><Collection /></el-icon></div>
              <div class="kb-list-info">
                <div class="kb-list-name">{{ kb.name }}</div>
                <div class="kb-list-meta">{{ kb.doc_count }} 个文档</div>
              </div>
              <el-button text size="small" @click.stop="deleteKB(kb)" :icon="Delete" />
            </div>
            <div v-if="!loadingKBs && !knowledgeBases.length" class="kb-list-empty">暂无知识库</div>
          </div>
        </div>

        <div v-else>
          <div class="kb-left-title-row">
            <el-button text size="small" @click="selectedKBId = null; kbDocuments = []" :icon="ArrowLeft" />
            <span class="kb-left-title">{{ selectedKB?.name }}</span>
            <el-button size="small" type="primary" text @click="openAddDialog" :icon="Upload">添加</el-button>
          </div>
          <div class="kb-doc-list">
            <div v-if="loadingDocs" class="kb-list-loading">加载中...</div>
            <div v-for="doc in kbDocuments" :key="doc.filename" class="kb-doc-item">
              <div class="kb-doc-icon"><el-icon><Document /></el-icon></div>
              <div class="kb-doc-info">
                <div class="kb-doc-name" :title="doc.filename">{{ doc.filename }}</div>
                <div class="kb-doc-meta">{{ doc.chunk_count }} 个分块 · {{ getStatusLabel(doc.status) }}</div>
              </div>
              <el-button text size="small" @click="removeDocument(doc.filename)" :icon="Delete" />
            </div>
            <div v-if="!loadingDocs && !kbDocuments.length" class="kb-list-empty">暂无文档</div>
          </div>
          <div class="kb-doc-actions">
            <el-button size="small" text type="primary" @click="goToDetail(selectedKB!)">查看详情</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Right panel: chat -->
    <div class="kb-right">
      <div ref="messagesContainer" class="messages">
        <div v-if="!chatStore.messages.length" class="empty">
          <div class="empty-icon">
            <el-icon :size="48"><Collection /></el-icon>
          </div>
          <h3>在知识库中提问</h3>
          <p>选择一个知识库，开始对话</p>
        </div>

        <MessageBubble
          v-for="(msg, i) in chatStore.messages"
          :key="i"
          :message="msg"
          :index="i"
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

    <!-- Create KB dialog -->
    <el-dialog v-model="showCreateDialog" title="创建知识库" width="420px" :close-on-click-modal="false" @closed="newKBName = ''">
      <el-input v-model="newKBName" placeholder="输入知识库名称" maxlength="100" @keyup.enter="createKB" />
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createKB">创建</el-button>
      </template>
    </el-dialog>

    <!-- Add file dialog -->
    <el-dialog v-model="showAddDialog" title="添加文件到知识库" width="520px" :close-on-click-modal="false">
      <div v-if="loadingFiles" class="kb-dialog-center">加载中...</div>
      <div v-else-if="!availableFiles.length" class="kb-dialog-center">暂无可添加的文件</div>
      <div v-else class="kb-add-list">
        <div
          v-for="file in availableFiles"
          :key="file.name"
          :class="['kb-add-item', { active: selectedAddFile?.name === file.name }]"
          @click="selectedAddFile = file"
        >
          <span class="kb-add-name">{{ file.name }}</span>
          <span class="kb-add-meta">{{ file.size_human }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="addingFile" :disabled="!selectedAddFile" @click="addFileToKB">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.kb-mode {
  display: flex;
  height: 100%;
}

/* ── Left Panel ───────────────────────────────────────── */
.kb-left {
  width: 300px;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.kb-left-header {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
  overflow: hidden;
}

.kb-left-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.kb-left-title {
  font-family: var(--font-heading);
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
  flex: 1;
  margin-left: var(--space-2);
}

/* ── KB List ──────────────────────────────────────────── */
.kb-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kb-list-loading {
  text-align: center;
  color: var(--color-secondary);
  font-size: var(--text-sm);
  padding: var(--space-8) 0;
}

.kb-list-empty {
  text-align: center;
  color: var(--color-secondary);
  font-size: var(--text-sm);
  padding: var(--space-8) 0;
}

.kb-list-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.kb-list-item:hover {
  background: var(--color-muted);
}

.kb-list-icon {
  width: 32px;
  height: 32px;
  background: var(--color-accent-light);
  color: var(--color-accent);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;
}

.kb-list-info {
  flex: 1;
  min-width: 0;
}

.kb-list-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-foreground);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kb-list-meta {
  font-size: var(--text-xs);
  color: var(--color-secondary);
  margin-top: 2px;
}

/* ── Doc List ─────────────────────────────────────────── */
.kb-doc-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kb-doc-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius);
  transition: background var(--duration-fast);
}

.kb-doc-item:hover {
  background: var(--color-muted);
}

.kb-doc-icon {
  color: var(--color-secondary);
  flex-shrink: 0;
}

.kb-doc-info {
  flex: 1;
  min-width: 0;
}

.kb-doc-name {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--color-foreground);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kb-doc-meta {
  font-size: 10px;
  color: var(--color-secondary);
}

.kb-doc-actions {
  padding: var(--space-3) 0 0;
  border-top: 1px solid var(--color-border);
  margin-top: var(--space-2);
}

/* ── Right Panel ──────────────────────────────────────── */
.kb-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-background);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-8) 0;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--color-secondary);
}

.empty-icon {
  color: var(--color-border);
  margin-bottom: var(--space-4);
}

.empty h3 {
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
  margin-bottom: var(--space-2);
}

.empty p {
  font-size: var(--text-base);
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
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
  font-weight: var(--font-bold);
}

.ai-avatar {
  background: var(--color-foreground);
  color: white;
  font-family: var(--font-mono);
  font-size: 13px;
}

.msg-body {
  flex: 1;
  min-width: 0;
  max-width: 85%;
}

.typing {
  display: flex;
  gap: 6px;
  padding: var(--space-5);
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
  padding: 0 var(--space-6) var(--space-4);
}

.suggest-btn {
  padding: var(--space-2) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  color: var(--color-secondary);
  cursor: pointer;
  font-family: var(--font-body);
  transition: all var(--duration-normal) var(--ease-out);
}

.suggest-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

/* ── Dialog helpers ───────────────────────────────────── */
.kb-dialog-center {
  text-align: center;
  padding: var(--space-8) 0;
  color: var(--color-secondary);
  font-size: var(--text-sm);
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
  transition: all var(--duration-fast) var(--ease-out);
}

.kb-add-item:hover,
.kb-add-item.active {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.kb-add-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-foreground);
}

.kb-add-meta {
  font-size: var(--text-xs);
  color: var(--color-secondary);
}
</style>
