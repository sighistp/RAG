<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useFilesStore } from '../stores/files'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'

const filesStore = useFilesStore()
const dragover = ref(false)

onMounted(() => { filesStore.loadFiles() })

function getFileIcon(ext: string): string {
  const map: Record<string, string> = { '.pdf': '📕', '.docx': '📘', '.xlsx': '📊', '.csv': '📊', '.md': '📝', '.txt': '📄' }
  return map[ext] || '📄'
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
    await ElMessageBox.confirm(`确定删除文件 "${name}"？`, '确认删除', { type: 'warning' })
    await filesStore.deleteFile(name)
    ElMessage.success('文件已删除')
  } catch {}
}

function handleDragover(e: DragEvent) { e.preventDefault(); dragover.value = true }
function handleDragleave() { dragover.value = false }

async function handleDrop(e: DragEvent) {
  e.preventDefault(); dragover.value = false
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
    <div :class="['drop-zone', { active: dragover }]" @dragover="handleDragover" @dragleave="handleDragleave" @drop="handleDrop">
      <div class="drop-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
        </svg>
      </div>
      <h3>拖拽文件到此处上传</h3>
      <p>支持 txt、md、pdf、docx、xlsx、csv</p>
      <el-upload :show-file-list="false" :before-upload="() => false" :on-change="handleUpload" accept=".txt,.md,.pdf,.docx,.xlsx,.csv">
        <el-button type="primary">选择文件</el-button>
      </el-upload>
    </div>

    <div class="grid">
      <div v-for="file in filesStore.files" :key="file.name" class="file-card">
        <div class="file-icon">{{ getFileIcon(file.ext) }}</div>
        <div class="file-name">{{ file.name }}</div>
        <div class="file-size">{{ file.size_human }}</div>
        <button class="file-delete" @click="handleDelete(file.name)" title="删除">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
            <line x1="3" y1="3" x2="11" y2="11"/><line x1="11" y1="3" x2="3" y2="11"/>
          </svg>
        </button>
      </div>

      <div v-if="!filesStore.files.length && !filesStore.loading" class="empty">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
          <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
        </svg>
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

.drop-icon { color: var(--color-secondary); margin-bottom: var(--space-4); }

.drop-zone h3 {
  font-family: var(--font-heading);
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-foreground);
  margin-bottom: var(--space-2);
}

.drop-zone p {
  font-size: var(--text-sm);
  color: var(--color-secondary);
  margin-bottom: var(--space-4);
}

.grid {
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
  transition: all var(--duration-normal) var(--ease-out);
  cursor: pointer;
  animation: slideUp 0.3s var(--ease-out);
}

.file-card:hover {
  border-color: var(--color-border-hover);
  box-shadow: var(--shadow);
  transform: translateY(-2px);
}

.file-icon { font-size: 28px; margin-bottom: var(--space-3); }

.file-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-foreground);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: var(--space-1);
}

.file-size { font-size: var(--text-xs); color: var(--color-secondary); }

.file-delete {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  color: var(--color-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  opacity: 0;
  transition: all var(--duration-fast);
}

.file-card:hover .file-delete { opacity: 1; }
.file-delete:hover { background: var(--color-destructive-light); color: var(--color-destructive); }

.empty {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-12);
  color: var(--color-secondary);
}
</style>
