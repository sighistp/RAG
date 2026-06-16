import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      component: () => import('../views/MainLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/files'
        },
        {
          path: 'files',
          name: 'files',
          component: () => import('../views/FileModeView.vue')
        },
        {
          path: 'kb',
          name: 'kb',
          component: () => import('../views/KBModeView.vue')
        },
        {
          path: 'kb/:id',
          name: 'kb-detail',
          component: () => import('../views/KnowledgeDetailView.vue')
        },
        {
          path: 'analysis',
          name: 'analysis',
          component: () => import('../views/AnalysisModeView.vue')
        }
      ]
    }
  ]
})

// Navigation guard
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth !== false && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.name === 'login' && authStore.isAuthenticated) {
    next('/')
  } else {
    next()
  }
})

export default router
