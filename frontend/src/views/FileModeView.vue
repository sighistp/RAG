<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { useFilesStore } from '../stores/files'
import MessageBubble from '../components/MessageBubble.vue'
import ChatInput from '../components/ChatInput.vue'

const chatStore = useChatStore()
const filesStore = useFilesStore()
const messagesContainer = ref<HTMLElement>()

onMounted(() => {
  filesStore.loadFiles()
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
</script>

<template>
  <div class="file-mode">
    <!-- File management area -->
    <div class="file-section">
      <div class="file-section-header">
        <span class="section-label">检索范围</span>
        <el-upload :show-file-list="false" :before-upload="() => false" :on-change="(f: any) => filesStore.uploadFile(f.raw!)" accept=".txt,.md,.pdf,.docx,.xlsx,.csv">
          <el-button size="small" type="primary" text>上传文件</el-button>
        </el-upload>
      </div>
      <div class="file-list">
        <div
          :class="['file-chip', { active: chatStore.selectedFile === null }]"
          @click="chatStore.selectFile(null)"
        >
          <span class="file-chip-icon">🔍</span>
          <span>全部文件</span>
        </div>
        <div
          v-for="file in filesStore.files"
          :key="file.name"
          :class="['file-chip', { active: chatStore.selectedFile === file.name }]"
          @click="chatStore.selectFile(file.name)"
        >
          <span class="file-chip-icon">📄</span>
          <span class="file-chip-name" :title="file.name">{{ file.name }}</span>
        </div>
      </div>
    </div>

    <!-- Chat area -->
    <div class="chat-section">
      <div ref="messagesContainer" class="messages">
        <div v-if="!chatStore.messages.length" class="empty">
          <div class="empty-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
            </svg>
          </div>
          <h3>开始一个新对话</h3>
          <p>上传文档后，向知识库提问</p>
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
            <div class="typing">
              <span></span><span></span><span></span>
            </div>
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
</template>

<style scoped>
.file-mode {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* ── File Section ─────────────────────────────────────── */
.file-section {
  padding: var(--space-3) var(--space-6);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.file-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.section-label {
  font-size: 11px;
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-secondary);
}

.file-list {
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  padding-bottom: var(--space-1);
}

.file-chip {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  color: var(--color-secondary);
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--duration-fast) var(--ease-out);
  flex-shrink: 0;
}

.file-chip:hover {
  border-color: var(--color-accent);
  color: var(--color-foreground);
}

.file-chip.active {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
  color: var(--color-accent);
  font-weight: var(--font-medium);
}

.file-chip-icon {
  font-size: 12px;
}

.file-chip-name {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Chat Section ─────────────────────────────────────── */
.chat-section {
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

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--color-secondary);
  animation: fadeIn 0.5s var(--ease-out);
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
