<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useFilesStore } from '../stores/files'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'

const filesStore = useFilesStore()
const dragover = ref(false)

onMounted(() => {
  filesStore.loadFiles()
})

function getFileIcon(ext: string): string {
  const icons: Record<string, string> = {
    '.pdf': '📕',
    '.docx': '📘',
    '.xlsx': '📊',
    '.csv': '📊',
    '.md': '📝',
    '.txt': '📄'
  }
  return icons[ext] || '📄'
}

async function handleUpload(file: UploadFile) {
  try {
    await filesStore.uploadFile(file.raw!)
    ElMessage.success(`文件 ${file.name} 上传成功`)
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '上传失败')
  }
}

async function handleDelete(name: string) {
  try {
    await ElMessageBox.confirm(`确定删除文件 "${name}"？`, '确认删除', {
      type: 'warning'
    })
    await filesStore.deleteFile(name)
    ElMessage.success('文件已删除')
  } catch {
    // User cancelled
  }
}

function handleDragover(e: DragEvent) {
  e.preventDefault()
  dragover.value = true
}

function handleDragleave() {
  dragover.value = false
}

async function handleDrop(e: DragEvent) {
  e.preventDefault()
  dragover.value = false
  const file = e.dataTransfer?.files[0]
  if (file) {
    try {
      await filesStore.uploadFile(file)
      ElMessage.success(`文件 ${file.name} 上传成功`)
    } catch (err: any) {
      ElMessage.error(err.response?.data?.detail || '上传失败')
    }
  }
}
</script>

<template>
  <div class="files-page">
    <!-- Upload area -->
    <div
      :class="['drop-zone', { active: dragover }]"
      @dragover="handleDragover"
      @dragleave="handleDragleave"
      @drop="handleDrop"
    >
      <el-icon class="drop-icon"><Upload /></el-icon>
      <h3 class="drop-title">拖拽文件到此处上传</h3>
      <p class="drop-hint">支持 txt、md、pdf、docx、xlsx、csv</p>
      <el-upload
        :show-file-list="false"
        :before-upload="() => false"
        :on-change="handleUpload"
        accept=".txt,.md,.pdf,.docx,.xlsx,.csv"
      >
        <el-button type="primary" class="upload-btn">
          <el-icon><Upload /></el-icon>
          选择文件
        </el-button>
      </el-upload>
    </div>

    <!-- Files grid -->
    <div class="files-grid">
      <div
        v-for="file in filesStore.files"
        :key="file.name"
        class="file-card"
      >
        <div class="file-icon">{{ getFileIcon(file.ext) }}</div>
        <div class="file-name">{{ file.name }}</div>
        <div class="file-size">{{ file.size_human }}</div>
        <el-button
          class="file-delete"
          size="small"
          circle
          @click="handleDelete(file.name)"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>

      <div v-if="!filesStore.files.length && !filesStore.loading" class="empty-files">
        <el-icon class="empty-icon"><FolderOpened /></el-icon>
        <p>暂无文件</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.files-page {
  padding: var(--space-6);
  overflow-y: auto;
  height: 100%;
}

.drop-zone {
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-12) var(--space-6);
  text-align: center;
  transition: all var(--duration-normal) var(--ease-out);
  margin-bottom: var(--space-6);
}

.drop-zone.active {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.drop-icon {
  font-size: 48px;
  color: var(--color-secondary);
  margin-bottom: var(--space-4);
}

.drop-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
  margin-bottom: var(--space-2);
}

.drop-hint {
  font-size: var(--text-sm);
  color: var(--color-secondary);
  margin-bottom: var(--space-4);
}

.upload-btn {
  height: 40px;
}

.files-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-4);
}

.file-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-5);
  position: relative;
  transition: all var(--duration-fast) var(--ease-out);
  cursor: pointer;
}

.file-card:hover {
  border-color: var(--color-accent);
  box-shadow: var(--shadow);
}

.file-icon {
  font-size: 32px;
  margin-bottom: var(--space-3);
}

.file-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-foreground);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: var(--space-1);
}

.file-size {
  font-size: var(--text-xs);
  color: var(--color-secondary);
}

.file-delete {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  opacity: 0;
  transition: opacity var(--duration-fast);
}

.file-card:hover .file-delete {
  opacity: 1;
}

.empty-files {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-12);
  color: var(--color-secondary);
}

.empty-icon {
  font-size: 48px;
  color: var(--color-border);
}
</style>
