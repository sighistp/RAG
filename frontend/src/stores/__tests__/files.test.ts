import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useFilesStore } from '../files'

vi.mock('../../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn()
  }
}))

vi.mock('../auth', () => ({
  useAuthStore: vi.fn(() => ({
    token: 'test-token',
    getAuthHeaders: () => ({ Authorization: 'Bearer test-token' })
  }))
}))

import api from '../../utils/api'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('files store', () => {
  it('loadFiles fills the list', async () => {
    const files = [
      { name: 'doc.pdf', size: 1024, size_human: '1 KB', ext: '.pdf' },
      { name: 'data.csv', size: 2048, size_human: '2 KB', ext: '.csv' }
    ]
    vi.mocked(api.get).mockResolvedValue({ data: { files } } as any)

    const store = useFilesStore()
    await store.loadFiles()

    expect(store.files).toEqual(files)
  })

  it('uploadFile calls /upload', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { success: true } } as any)
    vi.mocked(api.get).mockResolvedValue({ data: { files: [] } } as any)

    const store = useFilesStore()
    const fakeFile = new File(['content'], 'test.txt', { type: 'text/plain' })
    await store.uploadFile(fakeFile)

    expect(api.post).toHaveBeenCalledWith(
      '/upload',
      expect.any(FormData),
      expect.anything()
    )
  })

  it('deleteFile calls DELETE /files/{name}', async () => {
    vi.mocked(api.delete).mockResolvedValue({} as any)
    vi.mocked(api.get).mockResolvedValue({ data: { files: [] } } as any)

    const store = useFilesStore()
    await store.deleteFile('my document.pdf')

    expect(api.delete).toHaveBeenCalledWith(
      '/files/my%20document.pdf',
      expect.anything()
    )
  })
})
