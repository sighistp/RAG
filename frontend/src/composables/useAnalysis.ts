import { ref } from 'vue'
import api from '../utils/api'
import { useAuthStore } from '../stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

interface CardGroup {
  id: number
  name: string
  questions: Array<{ id: number; question: string }>
}

/**
 * Composable for adding messages to analysis card groups.
 * Logic: if card groups exist, add directly; if none, prompt to create one first.
 */
export function useAnalysis() {
  const loading = ref(false)

  async function addToAnalysis(answerContent: string) {
    const auth = useAuthStore()
    loading.value = true

    try {
      // 1. Fetch existing card groups
      const res = await api.get('/analysis/cards', { headers: auth.getAuthHeaders() })
      const cards: CardGroup[] = res.data || []

      if (cards.length > 0) {
        // 2a. Cards exist — add directly to the first card
        await api.post(`/analysis/cards/${cards[0].id}/questions`, {
          question: answerContent
        }, { headers: auth.getAuthHeaders() })
        ElMessage.success(`已添加到卡片组「${cards[0].name}」`)
      } else {
        // 2b. No cards — prompt to create one
        try {
          await ElMessageBox.confirm(
            '暂无卡片组，需要先创建一个卡片组才能添加问题。',
            '创建卡片组',
            {
              confirmButtonText: '创建',
              cancelButtonText: '取消',
              type: 'info'
            }
          )
          // Create a new card group
          const createRes = await api.post('/analysis/cards', {
            name: '新建卡片组'
          }, { headers: auth.getAuthHeaders() })
          const newCard = createRes.data

          // Add the question to the new card
          await api.post(`/analysis/cards/${newCard.id}/questions`, {
            question: answerContent
          }, { headers: auth.getAuthHeaders() })
          ElMessage.success('已创建卡片组并添加问题')
        } catch {
          // User cancelled
        }
      }
    } catch {
      ElMessage.error('添加到分析失败')
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    addToAnalysis
  }
}
