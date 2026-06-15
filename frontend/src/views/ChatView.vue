<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()
const inputText = ref('')
const messagesContainer = ref<HTMLElement>()

watch(() => chatStore.messages.length, () => {
  nextTick(() => { messagesContainer.value?.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' }) })
})

watch(() => chatStore.messages[chatStore.messages.length - 1]?.content, () => {
  nextTick(() => { messagesContainer.value?.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' }) })
})

async function handleSend() {
  const q = inputText.value.trim()
  if (!q || chatStore.isStreaming) return
  inputText.value = ''
  await chatStore.sendMessage(q)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
}

function askSuggested(q: string) { inputText.value = q; handleSend() }

function formatContent(text: string): string {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
    .replace(/\[([^\]]+)\]/g, '<span class="ref">$1</span>')
}
</script>

<template>
  <div class="chat">
    <div ref="messagesContainer" class="messages">
      <!-- Empty state -->
      <div v-if="!chatStore.messages.length" class="empty">
        <div class="empty-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
        </div>
        <h3>开始一个新对话</h3>
        <p>上传文档后，向知识库提问</p>
      </div>

      <!-- Messages -->
      <div
        v-for="(msg, i) in chatStore.messages"
        :key="i"
        :class="['msg', msg.role]"
      >
        <div v-if="msg.role === 'user'" class="msg-avatar user-avatar">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 8a3 3 0 100-6 3 3 0 000 6zm5 6a5 5 0 00-10 0h10z"/>
          </svg>
        </div>
        <div v-else class="msg-avatar ai-avatar">R</div>

        <div class="msg-body">
          <div class="bubble" v-html="formatContent(msg.content)" />

          <!-- Sources -->
          <div v-if="msg.sources?.length" class="sources">
            <span v-for="(src, j) in msg.sources" :key="j" class="source-chip">
              {{ j + 1 }}. {{ src.doc_name }}
            </span>
          </div>

          <!-- Actions -->
          <div v-if="msg.role === 'assistant' && msg.content" class="actions">
            <button
              :class="['action-btn', { active: msg.feedback === 'positive' }]"
              @click="chatStore.sendFeedback(i, 'positive')"
              title="有用"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M4 13V6L7 2l4 4v7H4z"/>
              </svg>
            </button>
            <button
              :class="['action-btn', { active: msg.feedback === 'negative' }]"
              @click="chatStore.sendFeedback(i, 'negative')"
              title="没用"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M10 1V8L7 12l-4-4V1h7z" transform="rotate(180 7 7)"/>
              </svg>
            </button>
            <button class="action-btn" @click="chatStore.regenerate(i)" :disabled="chatStore.isStreaming" title="重新生成">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M1 7a6 6 0 0111.5-2.3M13 7a6 6 0 01-11.5 2.3"/>
                <path d="M13 1v4h-4M1 13v-4h4"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Typing -->
      <div v-if="chatStore.isStreaming && !chatStore.messages[chatStore.messages.length - 1]?.content" class="msg assistant">
        <div class="msg-avatar ai-avatar">R</div>
        <div class="msg-body">
          <div class="typing">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Suggestions -->
    <div v-if="chatStore.suggestedQuestions.length" class="suggestions">
      <button v-for="q in chatStore.suggestedQuestions" :key="q" class="suggest-btn" @click="askSuggested(q)">
        {{ q }}
      </button>
    </div>

    <!-- Input -->
    <div class="input-area">
      <div class="input-box">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="1"
          :autosize="{ minRows: 1, maxRows: 5 }"
          placeholder="输入你的问题..."
          @keydown="handleKeydown"
          :disabled="chatStore.isStreaming"
        />
        <button class="send-btn" :disabled="!inputText.trim() || chatStore.isStreaming" @click="handleSend">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M16 2L8 10M16 2l-5 14-3-7-7-3 14-4z"/>
          </svg>
        </button>
      </div>
      <div class="input-hint">Enter 发送 · Shift + Enter 换行</div>
    </div>
  </div>
</template>

<style scoped>
.chat {
  display: flex;
  flex-direction: column;
  height: 100%;
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

/* ── Message ──────────────────────────────────────────── */
.msg {
  display: flex;
  gap: var(--space-4);
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-3) var(--space-6);
  animation: slideUp 0.3s var(--ease-out);
}

.msg.user {
  flex-direction: row-reverse;
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

.user-avatar {
  background: var(--color-accent-light);
  color: var(--color-accent);
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

.msg.user .msg-body {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

/* ── Bubble ───────────────────────────────────────────── */
.bubble {
  padding: var(--space-4) var(--space-5);
  border-radius: var(--radius-lg);
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  word-break: break-word;
}

.msg.user .bubble {
  background: var(--color-foreground);
  color: white;
  border-bottom-right-radius: var(--radius-sm);
}

.msg.assistant .bubble {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-bottom-left-radius: var(--radius-sm);
}

:deep(.ref) {
  display: inline;
  padding: 1px 6px;
  background: var(--color-accent-light);
  color: var(--color-accent);
  border-radius: 4px;
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

/* ── Sources ──────────────────────────────────────────── */
.sources {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.source-chip {
  padding: var(--space-1) var(--space-3);
  background: var(--color-muted);
  color: var(--color-secondary);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.source-chip:hover {
  background: var(--color-accent-light);
  color: var(--color-accent);
}

/* ── Actions ──────────────────────────────────────────── */
.actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
  opacity: 0;
  transition: opacity var(--duration-fast);
}

.msg:hover .actions {
  opacity: 1;
}

.action-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: var(--radius-sm);
  color: var(--color-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.action-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.action-btn.active {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: white;
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Typing ───────────────────────────────────────────── */
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

/* ── Input ────────────────────────────────────────────── */
.input-area {
  padding: var(--space-4) var(--space-6) var(--space-6);
  background: linear-gradient(to top, var(--color-background) 60%, transparent);
}

.input-box {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  gap: var(--space-3);
  align-items: flex-end;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-3) var(--space-3) var(--space-4);
  box-shadow: var(--shadow);
  transition: all var(--duration-normal) var(--ease-out);
}

.input-box:focus-within {
  border-color: var(--color-accent);
  box-shadow: var(--shadow), 0 0 0 3px var(--color-accent-light);
}

:deep(.el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  padding: var(--space-2) 0 !important;
  font-family: var(--font-body) !important;
  font-size: var(--text-base) !important;
  resize: none !important;
  background: transparent !important;
}

.send-btn {
  width: 40px;
  height: 40px;
  background: var(--color-accent);
  border: none;
  border-radius: var(--radius);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all var(--duration-normal) var(--ease-out);
}

.send-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-accent);
}

.send-btn:disabled {
  background: var(--color-border);
  cursor: not-allowed;
}

.input-hint {
  text-align: center;
  font-size: var(--text-xs);
  color: var(--color-secondary);
  margin-top: var(--space-2);
  opacity: 0.7;
}
</style>
