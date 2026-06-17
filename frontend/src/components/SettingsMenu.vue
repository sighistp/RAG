<script setup lang="ts">
import { ElDropdown, ElDropdownMenu, ElDropdownItem } from 'element-plus'

defineProps<{
  summary: string
}>()

const emit = defineEmits<{
  (e: 'edit-name'): void
  (e: 'generate-summary'): void
  (e: 'add-content'): void
  (e: 'export'): void
  (e: 'delete-summary'): void
  (e: 'delete-card'): void
}>()
</script>

<template>
  <el-dropdown trigger="click" @command="(cmd: string) => emit(cmd as any)">
    <button class="settings-btn" @click.stop title="设置">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="8" cy="8" r="2"/>
        <path d="M13.5 8a5.5 5.5 0 01-.3 1.8l1.3.8-.9 1.6-1.5-.3a5.5 5.5 0 01-1.6 1l.1 1.7h-1.8l.1-1.7a5.5 5.5 0 01-1.6-1l-1.5.3-.9-1.6 1.3-.8A5.5 5.5 0 015.5 8a5.5 5.5 0 01.3-1.8L4.5 5.4l.9-1.6 1.5.3a5.5 5.5 0 011.6-1L8.4 1.4h1.8l-.1 1.7a5.5 5.5 0 011.6 1l1.5-.3.9 1.6-1.3.8c.2.6.3 1.2.3 1.8z"/>
      </svg>
    </button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="edit-name">编辑名称</el-dropdown-item>
        <el-dropdown-item command="generate-summary">生成摘要</el-dropdown-item>
        <el-dropdown-item command="add-content">添加内容</el-dropdown-item>
        <el-dropdown-item command="export">导出为 Markdown</el-dropdown-item>
        <el-dropdown-item v-if="summary" command="delete-summary" divided>删除摘要</el-dropdown-item>
        <el-dropdown-item command="delete-card" divided>删除卡片</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<style scoped>
.settings-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: var(--radius-sm);
  color: var(--color-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.settings-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
</style>
