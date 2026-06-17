import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../../stores/auth', () => ({
  useAuthStore: vi.fn(() => ({
    token: 'test-token',
    getAuthHeaders: () => ({ Authorization: 'Bearer test-token' })
  }))
}))

vi.mock('../../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn() },
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve()) }
}))

import api from '../../utils/api'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AnalysisModeView export', () => {
  it('export calls GET /analysis/cards/{id}/export with markdown format', async () => {
    const mockBlob = new Blob(['# Test Card\n'], { type: 'text/markdown' })
    vi.mocked(api.get).mockResolvedValue({ data: mockBlob } as any)

    const exportResp = await api.get('/analysis/cards/1/export?format=markdown', {
      headers: { Authorization: 'Bearer test-token' },
      responseType: 'blob',
    })

    expect(api.get).toHaveBeenCalledWith(
      '/analysis/cards/1/export?format=markdown',
      expect.objectContaining({
        headers: { Authorization: 'Bearer test-token' },
        responseType: 'blob',
      })
    )
    expect(exportResp.data).toBeInstanceOf(Blob)
  })

  it('export card creates download link with correct filename', async () => {
    const mockClick = vi.fn()
    const mockRevoke = vi.fn()
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(mockRevoke)
    vi.spyOn(document, 'createElement').mockReturnValue({ click: mockClick, href: '', download: '' } as any)

    const cardName = '测试卡片'
    const blob = new Blob(['content'], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${cardName}.md`
    a.click()

    expect(mockClick).toHaveBeenCalled()
    expect(a.download).toBe('测试卡片.md')
    URL.revokeObjectURL(url)
    expect(mockRevoke).toHaveBeenCalledWith('blob:mock')
  })
})
