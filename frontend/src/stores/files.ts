import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'
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

  async function loadFiles() {
    loading.value = true
    try {
      const res = await axios.get(`${API}/files`)
      files.value = res.data.files
    } finally {
      loading.value = false
    }
  }

  async function uploadFile(file: File) {
    const auth = useAuthStore()
    const formData = new FormData()
    formData.append('file', file)

    const res = await axios.post(`${API}/upload`, formData, {
      headers: {
        ...auth.getAuthHeaders(),
        'Content-Type': 'multipart/form-data'
      }
    })

    await loadFiles()
    return res.data
  }

  async function deleteFile(name: string) {
    const auth = useAuthStore()
    await axios.delete(`${API}/files/${encodeURIComponent(name)}`, {
      headers: auth.getAuthHeaders()
    })
    await loadFiles()
  }

  return {
    files,
    loading,
    loadFiles,
    uploadFile,
    deleteFile
  }
})
