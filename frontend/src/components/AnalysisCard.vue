<script setup lang="ts">
import { ref } from 'vue'
import { Delete, Plus, ArrowDown, ArrowRight } from '@element-plus/icons-vue'
import SettingsMenu from './SettingsMenu.vue'

interface Question {
  id: number
  question: string
}

const props = defineProps<{
  cardId: number
  title: string
  questions: Question[]
  summary?: string
}>()

const emit = defineEmits<{
  (e: 'update:title', value: string): void
  (e: 'add-question', value: string): void
  (e: 'remove-question', questionId: number): void
  (e: 'generate-summary'): void
  (e: 'update-summary', value: string): void
  (e: 'delete-summary'): void
  (e: 'delete-card'): void
  (e: 'add-content'): void
}>()

const editing = ref(false)
const titleDraft = ref('')
const newQuestion = ref('')
const collapsed = ref(false)
const showInput = ref(false)
const editingSummary = ref(false)
const summaryDraft = ref('')

function startEditTitle() {
  titleDraft.value = props.title
  editing.value = true
}

function saveTitle() {
  if (titleDraft.value.trim()) {
    emit('update:title', titleDraft.value.trim())
  }
  editing.value = false
}

function cancelEditTitle() {
  editing.value = false
}

function handleAddQuestion() {
  const q = newQuestion.value.trim()
  if (!q) return
  emit('add-question', q)
  newQuestion.value = ''
  showInput.value = false
}

function handleRemoveQuestion(questionId: number) {
  emit('remove-question', questionId)
}

function startEditSummary() {
  summaryDraft.value = props.summary || ''
  editingSummary.value = true
}

function saveSummary() {
  emit('update-summary', summaryDraft.value)
  editingSummary.value = false
}

function cancelEditSummary() {
  editingSummary.value = false
}

function handleSettingsCommand(command: string) {
  switch (command) {
    case 'edit-name':
      startEditTitle()
      break
    case 'generate-summary':
      emit('generate-summary')
      break
    case 'add-content':
      emit('add-content')
      break
    case 'delete-summary':
      emit('delete-summary')
      break
    case 'delete-card':
      emit('delete-card')
      break
  }
}
</script>

<template>
  <div class="analysis-card">
    <div class="card-header" @click="collapsed = !collapsed">
      <div class="card-header-left">
        <el-icon class="collapse-icon">
          <ArrowRight v-if="collapsed" />
          <ArrowDown v-else />
        </el-icon>
        <span v-if="!editing" class="card-title">{{ title }}</span>
        <el-input
          v-else
          v-model="titleDraft"
          size="small"
          @keyup.enter="saveTitle"
          @keyup.escape="cancelEditTitle"
          @blur="saveTitle"
          @click.stop
          autofocus
        />
      </div>
      <div class="card-header-right">
        <span class="card-count">{{ questions.length }} 个问题</span>
        <SettingsMenu
          :summary="summary || ''"
          @command="handleSettingsCommand"
          @edit-name="startEditTitle"
          @generate-summary="$emit('generate-summary')"
          @add-content="$emit('add-content')"
          @delete-summary="$emit('delete-summary')"
          @delete-card="$emit('delete-card')"
          @click.stop
        />
      </div>
    </div>

    <div v-if="!collapsed" class="card-body">
      <!-- Summary area -->
      <div v-if="summary || editingSummary" class="card-summary">
        <div v-if="editingSummary" class="summary-edit">
          <el-input
            v-model="summaryDraft"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 6 }"
            placeholder="输入摘要..."
            @keyup.escape="cancelEditSummary"
          />
          <div class="summary-edit-actions">
            <el-button size="small" @click="cancelEditSummary">取消</el-button>
            <el-button size="small" type="primary" @click="saveSummary">保存</el-button>
          </div>
        </div>
        <div v-else class="summary-display" @click.stop="startEditSummary">
          <span class="summary-label">摘要</span>
          <p class="summary-text">{{ summary }}</p>
        </div>
      </div>

      <div v-if="!questions.length" class="card-empty">暂无问题</div>
      <div v-for="q in questions" :key="q.id" class="card-question">
        <span class="question-text">{{ q.question }}</span>
        <button class="question-delete" @click="handleRemoveQuestion(q.id)" title="删除">
          <el-icon><Delete /></el-icon>
        </button>
      </div>

      <div v-if="showInput" class="card-add-input">
        <el-input
          v-model="newQuestion"
          size="small"
          placeholder="输入问题..."
          @keyup.enter="handleAddQuestion"
          @keyup.escape="showInput = false"
        />
        <el-button size="small" type="primary" @click="handleAddQuestion">添加</el-button>
      </div>
      <div v-else class="card-add-row">
        <button class="card-add-btn" @click="showInput = true">
          <el-icon><Plus /></el-icon> 添加问题
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.analysis-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  transition: all var(--duration-normal) var(--ease-out);
}

.analysis-card:hover {
  border-color: var(--color-border-hover);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  cursor: pointer;
  user-select: none;
  transition: background var(--duration-fast);
}

.card-header:hover {
  background: var(--color-muted);
}

.card-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.collapse-icon {
  color: var(--color-secondary);
  font-size: 14px;
  flex-shrink: 0;
}

.card-title {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
}

.card-count {
  font-size: var(--text-xs);
  color: var(--color-secondary);
}

.card-body {
  padding: 0 var(--space-5) var(--space-4);
}

.card-empty {
  color: var(--color-secondary);
  font-size: var(--text-sm);
  padding: var(--space-4) 0;
  text-align: center;
}

.card-question {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius);
  transition: background var(--duration-fast);
}

.card-question:hover {
  background: var(--color-muted);
}

.question-text {
  font-size: var(--text-sm);
  color: var(--color-foreground);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.question-delete {
  opacity: 0;
  border: none;
  background: none;
  color: var(--color-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast);
}

.card-question:hover .question-delete {
  opacity: 1;
}

.question-delete:hover {
  color: var(--color-destructive);
  background: var(--color-destructive-light);
}

.card-add-input {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.card-add-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-border);
}

.card-add-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  border: none;
  background: none;
  color: var(--color-accent);
  font-size: var(--text-sm);
  cursor: pointer;
  font-family: var(--font-body);
  padding: var(--space-1) 0;
  transition: opacity var(--duration-fast);
}

.card-add-btn:hover {
  opacity: 0.8;
}

.card-edit-btn {
  border: none;
  background: none;
  color: var(--color-secondary);
  font-size: var(--text-xs);
  cursor: pointer;
  font-family: var(--font-body);
  padding: var(--space-1) 0;
  transition: color var(--duration-fast);
}

.card-edit-btn:hover {
  color: var(--color-foreground);
}

/* ── Summary ──────────────────────────────────────────── */
.card-summary {
  margin-bottom: var(--space-3);
  padding: var(--space-3);
  background: var(--color-muted);
  border-radius: var(--radius);
  border-left: 3px solid var(--color-accent);
}

.summary-label {
  font-size: 10px;
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-accent);
  display: block;
  margin-bottom: var(--space-1);
}

.summary-text {
  font-size: var(--text-sm);
  color: var(--color-foreground);
  line-height: var(--leading-relaxed);
  margin: 0;
  cursor: pointer;
}

.summary-display:hover .summary-text {
  color: var(--color-accent);
}

.summary-edit-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
  justify-content: flex-end;
}
</style>
