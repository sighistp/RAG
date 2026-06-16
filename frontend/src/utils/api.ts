import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create()

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status } = error.response
      if (status === 401) {
        // Token expired or invalid -- clear and redirect to login
        localStorage.removeItem('rag_token')
        window.location.href = '/login'
        return Promise.reject(error)
      }
      if (status === 403) {
        ElMessage.error('权限不足，无法执行此操作')
      } else if (status >= 500) {
        ElMessage.error('服务器错误，请稍后重试')
      }
    } else if (error.message?.includes('Network Error') || error.code === 'ERR_NETWORK') {
      ElMessage.error('网络连接失败，请检查网络')
    }

    return Promise.reject(error)
  }
)

export default api
