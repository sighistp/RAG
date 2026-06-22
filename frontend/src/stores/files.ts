import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../utils/api'
import { useAuthStore } from './auth'

const API = ''

interface FileInfo {
  name: string
  size: number
  size_human: string
  ext: string
}

export const useFilesStore = defineStore('files', () => {
  const files = ref<FileInfo[]>([])
  const loading = ref(false)
  let _loaded = false

  async function loadFiles(force = false) {
    if (_loaded && !force) return
    loading.value = true
    try {
      const res = await api.get(`${API}/files`)
      files.value = Array.isArray(res.data?.files) ? res.data.files : []
      _loaded = true
    } catch {
      // Error already shown by global interceptor
    } finally {
      loading.value = false
    }
  }

  async function uploadFile(file: File, permissionLevel?: number) {
    const auth = useAuthStore()
    const formData = new FormData()
    formData.append('file', file)
    if (permissionLevel !== undefined) {
      formData.append('permission_level', String(permissionLevel))
    }

    const res = await api.post(`${API}/upload`, formData, {
      headers: auth.getAuthHeaders()
    })

    await loadFiles(true)
    return res.data
  }

  async function deleteFile(name: string) {
    const auth = useAuthStore()
    await api.delete(`${API}/files/${encodeURIComponent(name)}`, {
      headers: auth.getAuthHeaders()
    })
    await loadFiles(true)
  }

  return {
    files,
    loading,
    loadFiles,
    uploadFile,
    deleteFile
  }
})
