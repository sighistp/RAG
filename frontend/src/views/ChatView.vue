<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()
const inputText = ref('')
const messagesContainer = ref<HTMLElement>()

// Auto-scroll to bottom when messages change
watch(() => chatStore.messages.length, () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
})

// Also scroll during streaming
watch(() => chatStore.messages[chatStore.messages.length - 1]?.content, () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
})

async function handleSend() {
  const question = inputText.value.trim()
  if (!question || chatStore.isStreaming) return

  inputText.value = ''
  await chatStore.sendMessage(question)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function askSuggested(question: string) {
  inputText.value = question
  handleSend()
}

function handleFeedback(index: number, value: 'positive' | 'negative') {
  chatStore.sendFeedback(index, value)
}

function handleRegenerate(index: number) {
  chatStore.regenerate(index)
}

function formatContent(text: string): string {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
    .replace(/\[([^\]]+)\]/g, '<span class="source-ref">$1</span>')
}
</script>

<template>
  <div class="chat-container">
    <!-- Messages -->
    <div ref="messagesContainer" class="messages">
      <div v-if="!chatStore.messages.length" class="empty-state">
        <el-icon class="empty-icon"><ChatDotRound /></el-icon>
        <h3 class="empty-title">开始一个新对话</h3>
        <p class="empty-hint">上传文档后，向知识库提问</p>
      </div>

      <div
        v-for="(msg, index) in chatStore.messages"
        :key="index"
        :class="['message', msg.role]"
      >
        <div class="message-avatar">
          <template v-if="msg.role === 'user'">
            <el-icon><User /></el-icon>
          </template>
          <template v-else>
            <span class="ai-avatar">R</span>
          </template>
        </div>

        <div class="message-content">
          <div class="message-bubble" v-html="formatContent(msg.content)" />

          <!-- Sources -->
          <div v-if="msg.sources?.length" class="sources">
            <el-tag
              v-for="(src, i) in msg.sources"
              :key="i"
              size="small"
              type="info"
              class="source-tag"
            >
              [{{ i + 1 }}] {{ src.doc_name }}
            </el-tag>
          </div>

          <!-- Action buttons (for assistant messages) -->
          <div v-if="msg.role === 'assistant' && msg.content" class="actions">
            <el-button-group size="small">
              <el-button
                :type="msg.feedback === 'positive' ? 'success' : 'default'"
                @click="handleFeedback(index, 'positive')"
              >
                <el-icon><Select /></el-icon>
              </el-button>
              <el-button
                :type="msg.feedback === 'negative' ? 'danger' : 'default'"
                @click="handleFeedback(index, 'negative')"
              >
                <el-icon><CloseBold /></el-icon>
              </el-button>
            </el-button-group>
            <el-button
              size="small"
              @click="handleRegenerate(index)"
              :disabled="chatStore.isStreaming"
            >
              <el-icon><RefreshRight /></el-icon>
              重新生成
            </el-button>
          </div>
        </div>
      </div>

      <!-- Typing indicator -->
      <div v-if="chatStore.isStreaming && !chatStore.messages[chatStore.messages.length - 1]?.content" class="message assistant">
        <div class="message-avatar">
          <span class="ai-avatar">R</span>
        </div>
        <div class="message-content">
          <div class="typing-indicator">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Suggested questions -->
    <div v-if="chatStore.suggestedQuestions.length" class="suggestions">
      <el-button
        v-for="q in chatStore.suggestedQuestions"
        :key="q"
        class="suggest-btn"
        @click="askSuggested(q)"
      >
        {{ q }}
      </el-button>
    </div>

    <!-- Input area -->
    <div class="input-area">
      <div class="input-wrapper">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="1"
          :autosize="{ minRows: 1, maxRows: 6 }"
          placeholder="输入你的问题..."
          @keydown="handleKeydown"
          :disabled="chatStore.isStreaming"
          class="chat-input"
        />
        <el-button
          type="primary"
          :icon="Promotion"
          circle
          size="large"
          :disabled="!inputText.trim() || chatStore.isStreaming"
          @click="handleSend"
          class="send-btn"
        />
      </div>
      <div class="input-hint">Enter 发送，Shift + Enter 换行</div>
    </div>
  </div>
</template>

<script lang="ts">
import { Promotion } from '@element-plus/icons-vue'
export default { data: () => ({ Promotion }) }
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* ── Messages ─────────────────────────────────────────── */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6) 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--color-secondary);
}

.empty-icon {
  font-size: 64px;
  color: var(--color-border);
  margin-bottom: var(--space-4);
}

.empty-title {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
  margin-bottom: var(--space-2);
}

.empty-hint {
  font-size: var(--text-base);
  color: var(--color-secondary);
}

.message {
  display: flex;
  gap: var(--space-4);
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-4) var(--space-6);
  animation: slideUp var(--duration-slow) var(--ease-out);
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: var(--text-lg);
}

.message.user .message-avatar {
  background: var(--color-accent-light);
  color: var(--color-accent);
}

.ai-avatar {
  width: 36px;
  height: 36px;
  background: var(--color-primary);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-sm);
  font-weight: var(--font-bold);
  font-family: var(--font-mono);
}

.message-content {
  flex: 1;
  min-width: 0;
}

.message-bubble {
  padding: var(--space-4) var(--space-5);
  border-radius: var(--radius-lg);
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  word-break: break-word;
}

.message.user .message-bubble {
  background: var(--color-accent);
  color: white;
  border-bottom-right-radius: var(--radius-sm);
}

.message.assistant .message-bubble {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-bottom-left-radius: var(--radius-sm);
}

:deep(.source-ref) {
  display: inline;
  padding: 1px 6px;
  background: var(--color-accent-light);
  color: var(--color-accent);
  border-radius: var(--radius-sm);
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

.source-tag {
  font-size: var(--text-xs);
  cursor: pointer;
}

.source-tag:hover {
  background: var(--color-accent-light);
}

/* ── Actions ──────────────────────────────────────────── */
.actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
  opacity: 0;
  transition: opacity var(--duration-fast);
}

.message:hover .actions {
  opacity: 1;
}

/* ── Typing Indicator ─────────────────────────────────── */
.typing-indicator {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
}

.dot {
  width: 8px;
  height: 8px;
  background: var(--color-secondary);
  border-radius: 50%;
  animation: typingBounce 1.4s infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typingBounce {
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
  animation: slideUp var(--duration-slow) var(--ease-out);
}

.suggest-btn {
  font-size: var(--text-sm);
  border-radius: var(--radius-full);
}

/* ── Input Area ───────────────────────────────────────── */
.input-area {
  padding: var(--space-4) var(--space-6) var(--space-6);
  background: linear-gradient(to top, var(--color-background) 60%, transparent);
}

.input-wrapper {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  gap: var(--space-3);
  align-items: flex-end;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
  box-shadow: var(--shadow);
  transition: all var(--duration-normal) var(--ease-out);
}

.input-wrapper:focus-within {
  border-color: var(--color-accent);
  box-shadow: var(--shadow), 0 0 0 3px var(--color-accent-light);
}

.chat-input {
  flex: 1;
}

:deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  padding: var(--space-2) 0;
  font-family: var(--font-body);
  font-size: var(--text-base);
  resize: none;
}

.send-btn {
  flex-shrink: 0;
}

.input-hint {
  text-align: center;
  font-size: var(--text-xs);
  color: var(--color-secondary);
  margin-top: var(--space-2);
}
</style>
