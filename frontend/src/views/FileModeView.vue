<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { useFilesStore } from '../stores/files'
import { useAnalysis } from '../composables/useAnalysis'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Delete, FolderOpened, Plus } from '@element-plus/icons-vue'
import MessageBubble from '../components/MessageBubble.vue'
import ChatInput from '../components/ChatInput.vue'
import AddToAnalysisDialog from '../components/AddToAnalysisDialog.vue'

const chatStore = useChatStore()
const filesStore = useFilesStore()
const { addToAnalysis, dialogVisible, dialogQuestion, dialogAnswer, handleConfirm } = useAnalysis()
const messagesContainer = ref<HTMLElement>()
const dragover = ref(false)

function getFileIcon(ext: string): string {
  const icons: Record<string, string> = { '.pdf': '📕', '.docx': '📘', '.xlsx': '📊', '.csv': '📊', '.md': '📝', '.txt': '📄' }
  return icons[ext] || '📄'
}

const ALLOWED_EXTS = ['.txt', '.md', '.pdf', '.docx', '.xlsx', '.csv']

async function handleDrop(e: DragEvent) {
  dragover.value = false
  const droppedFiles = e.dataTransfer?.files
  if (!droppedFiles) return

  for (const file of Array.from(droppedFiles)) {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ALLOWED_EXTS.includes(ext)) {
      ElMessage.warning(`不支持的文件格式: ${file.name}`)
      continue
    }
    try {
      await filesStore.uploadFile(file)
      ElMessage.success(`文件 ${file.name} 上传成功`)
    } catch (err: any) {
      ElMessage.error(err.response?.data?.detail || `上传失败: ${file.name}`)
    }
  }
}

async function toggleVisibility(name: string) {
  try {
    const resp = await fetch(`/api/files/${encodeURIComponent(name)}/visibility`, {
      method: 'PUT',
      headers: { 'Authorization': `Bearer ${localStorage.getItem('rag_token')}` }
    })
    if (!resp.ok) throw new Error('切换失败')
    const data = await resp.json()
    // 更新本地状态
    const file = filesStore.files.find(f => f.name === name)
    if (file) file.is_public = data.is_public
    ElMessage.success(data.is_public ? '已设为公开' : '已设为私有')
  } catch (e: any) {
    ElMessage.error(e.message || '切换失败')
  }
}

async function handleDelete(name: string) {
  try {
    await ElMessageBox.confirm(`确定删除文件 "${name}"？`, '确认删除', { type: 'warning' })
    await filesStore.deleteFile(name)
    // Clear selected file if it was deleted
    if (chatStore.selectedFile === name) {
      chatStore.selectFile(null)
    }
    ElMessage.success('文件已删除')
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(async () => {
  await chatStore.loadConversations('file')
  // Auto-select the most recent conversation if exists
  if (chatStore.conversations.length > 0 && !chatStore.currentConvId) {
    await chatStore.selectConversation(chatStore.conversations[0].id)
  }
  filesStore.loadFiles()
})

watch(() => chatStore.messages.length, () => {
  nextTick(() => { messagesContainer.value?.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' }) })
})

watch(() => chatStore.messages[chatStore.messages.length - 1]?.content, () => {
  nextTick(() => { messagesContainer.value?.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' }) })
})

async function newConversation() {
  await chatStore.createConversation('file')
}

async function selectConversation(id: number) {
  await chatStore.selectConversation(id)
}

async function deleteConversation(id: number) {
  try {
    await ElMessageBox.confirm('确定删除这个对话？删除后不可恢复。', '确认删除', { type: 'warning' })
    await chatStore.deleteConversation(id)
  } catch {
    // User cancelled
  }
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
</script>

<template>
  <div class="file-mode">
    <!-- Conversation sidebar (left) -->
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

    <!-- File management panel (middle) -->
    <div class="file-panel">
      <div class="file-panel-header">
        <h1 class="file-panel-title">文件管理</h1>
        <div style="display: flex; align-items: center; gap: 8px;">
          <el-upload :show-file-list="false" :before-upload="() => false" :on-change="async (f: any) => { try { await filesStore.uploadFile(f.raw!); ElMessage.success('上传成功') } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '上传失败') } }" accept=".txt,.md,.pdf,.docx,.xlsx,.csv">
            <el-button size="small" type="primary">
              <el-icon><Upload /></el-icon>
              上传
            </el-button>
          </el-upload>
        </div>
      </div>

      <!-- Drop zone -->
      <div class="drop-zone" @dragover.prevent="dragover = true" @dragleave="dragover = false" @drop.prevent="handleDrop($event)" :class="{ active: dragover }">
        <el-icon class="drop-icon"><Upload /></el-icon>
        <p class="drop-text">拖拽文件到此处上传</p>
        <p class="drop-hint">支持 txt、md、pdf、docx、xlsx、csv</p>
      </div>

      <!-- File list -->
      <div class="file-list">
        <!-- "All files" option -->
        <div :class="['file-item', { selected: !chatStore.selectedFile }]" @click="chatStore.selectFile(null)">
          <div class="file-item-icon">📁</div>
          <div class="file-item-info">
            <div class="file-item-name">全部文件</div>
            <div class="file-item-size">搜索所有文件</div>
          </div>
        </div>
        <!-- Individual files -->
        <div v-for="file in filesStore.files" :key="file.name"
             :class="['file-item', { selected: chatStore.selectedFile === file.name }]"
             @click="chatStore.selectFile(file.name)">
          <div class="file-item-icon">{{ getFileIcon(file.ext) }}</div>
          <div class="file-item-info">
            <div class="file-item-name" :title="file.name">
              {{ file.name }}
              <span v-if="file.protected" class="protected-badge" title="受保护文件">🔒</span>
            </div>
            <div class="file-item-size">{{ file.size_human }}</div>
          </div>
          <div class="file-item-actions">
            <button v-if="file.is_owner && !file.protected" :class="['visibility-btn', { public: file.is_public }]"
                    @click.stop="toggleVisibility(file.name)" :title="file.is_public ? '公开 - 点击切换为私有' : '私有 - 点击切换为公开'">
              {{ file.is_public ? '公开' : '私有' }}
            </button>
            <span v-else-if="!file.protected" :class="['visibility-tag', { public: file.is_public }]">
              {{ file.is_public ? '公开' : '私有' }}
            </span>
            <button v-if="!file.protected" class="file-item-delete" @click.stop="handleDelete(file.name)" title="删除">
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </div>
        <div v-if="!filesStore.files.length" class="empty-files">
          <el-icon class="empty-icon"><FolderOpened /></el-icon>
          <p>暂无文件</p>
        </div>
      </div>
    </div>

    <!-- Chat area (right) -->
    <div class="chat-area">
      <div ref="messagesContainer" class="messages">
        <!-- No conversations at all -->
        <div v-if="!chatStore.conversations.length" class="empty-chat">
          <el-icon :size="48" style="color: var(--color-border);"><ChatDotRound /></el-icon>
          <h3>开始你的第一个对话</h3>
          <p>上传文档后，向知识库提问</p>
          <el-button type="primary" @click="newConversation" style="margin-top: 12px;">
            <el-icon style="margin-right: 6px;"><Plus /></el-icon>
            新建对话
          </el-button>
        </div>

        <!-- Conversation selected but no messages -->
        <div v-else-if="!chatStore.messages.length" class="empty-chat">
          <el-icon :size="48" style="color: var(--color-border);"><ChatDotRound /></el-icon>
          <h3>开始对话</h3>
          <p>在下方输入你的问题</p>
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

      <ChatInput v-if="chatStore.currentConvId" mode="file" />
    </div>

    <AddToAnalysisDialog
      v-model:visible="dialogVisible"
      :question="dialogQuestion"
      :answer="dialogAnswer"
      @confirm="handleConfirm"
    />
  </div>
</template>

<style scoped>
.file-mode {
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

/* ── File Panel (middle) ───────────────────────────────── */
.file-panel {
  width: 320px;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}

.file-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.file-panel-title {
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
  margin: 0;
}

.drop-zone {
  border: 2px dashed var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-4) var(--space-3);
  text-align: center;
  margin: var(--space-3) var(--space-4);
  transition: all var(--duration-normal) var(--ease-out);
  cursor: pointer;
}

.drop-zone:hover, .drop-zone.active {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.drop-icon {
  font-size: 24px;
  color: var(--color-secondary);
  margin-bottom: var(--space-1);
}

.drop-text {
  font-size: var(--text-sm);
  color: var(--color-foreground);
  margin-bottom: 2px;
}

.drop-hint {
  font-size: var(--text-xs);
  color: var(--color-secondary);
}

.file-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.file-item:hover {
  background: var(--color-muted);
}

.file-item.selected {
  background: var(--color-accent-light);
}

.file-item-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.file-item-info {
  flex: 1;
  min-width: 0;
}

.file-item-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-foreground);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-item-size {
  font-size: var(--text-xs);
  color: var(--color-secondary);
  margin-top: 1px;
}

.protected-badge {
  font-size: 12px;
  margin-left: 4px;
  vertical-align: middle;
}

.file-item-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.visibility-btn {
  font-size: var(--text-xs);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border);
  background: var(--color-muted);
  color: var(--color-secondary);
  cursor: pointer;
  transition: all var(--duration-fast);
  white-space: nowrap;
}

.visibility-btn.public {
  background: var(--color-accent-light);
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.visibility-btn:hover {
  background: var(--color-accent-subtle);
}

.visibility-tag {
  font-size: var(--text-xs);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-muted);
  color: var(--color-secondary);
  white-space: nowrap;
}

.visibility-tag.public {
  background: var(--color-accent-light);
  color: var(--color-accent);
}

.file-item-delete {
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

.file-item:hover .file-item-delete {
  opacity: 1;
}

.file-item-delete:hover {
  background: var(--color-destructive-light);
  color: var(--color-destructive);
}

.empty-files {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-8);
  color: var(--color-secondary);
}

.empty-icon {
  font-size: 24px;
  color: var(--color-border);
}

/* ── Chat Area (right) ─────────────────────────────────── */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-background);
}

/* ── Messages ─────────────────────────────────────────── */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-8) 0;
}

.empty-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--color-secondary);
  gap: var(--space-3);
}

.empty-chat h3 {
  font-family: var(--font-heading);
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
  margin: 0;
}

.empty-chat p {
  font-size: var(--text-sm);
  color: var(--color-secondary);
}

/* ── Typing ───────────────────────────────────────────── */
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

/* ── Suggestions ──────────────────────────────────────── */
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: 0 var(--space-6) var(--space-4);
  animation: slideUp 0.3s var(--ease-out);
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
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}
</style>
