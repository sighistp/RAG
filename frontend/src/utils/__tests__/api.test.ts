import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockInterceptorUse, mockAxiosInstance } = vi.hoisted(() => {
  const mockInterceptorUse = vi.fn()
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      response: { use: mockInterceptorUse }
    }
  }
  return { mockInterceptorUse, mockAxiosInstance }
})

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockAxiosInstance),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: { response: { use: vi.fn() } }
  }
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
    success: vi.fn()
  }
}))

import { ElMessage } from 'element-plus'

describe('api interceptor', () => {
  let responseErrorInterceptor: (error: any) => Promise<never>

  beforeEach(async () => {
    vi.clearAllMocks()
    vi.resetModules()
    localStorage.clear()
    await import('../api')
    const calls = mockInterceptorUse.mock.calls
    responseErrorInterceptor = calls[0]?.[1]
  })

  it('401 response clears token and rejects', async () => {
    localStorage.setItem('rag_token', 'expired')
    const error = { response: { status: 401 } }

    await expect(responseErrorInterceptor(error)).rejects.toBeDefined()

    expect(localStorage.getItem('rag_token')).toBeNull()
  })

  it('403 response shows permission error', async () => {
    const error = { response: { status: 403 } }

    await expect(responseErrorInterceptor(error)).rejects.toBeDefined()

    expect(ElMessage.error).toHaveBeenCalledWith('权限不足，无法执行此操作')
  })

  it('500 response shows server error', async () => {
    const error = { response: { status: 500 } }

    await expect(responseErrorInterceptor(error)).rejects.toBeDefined()

    expect(ElMessage.error).toHaveBeenCalledWith('服务器错误，请稍后重试')
  })
})
