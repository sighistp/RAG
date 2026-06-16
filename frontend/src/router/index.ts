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
          redirect: '/mode/file'
        },
        {
          path: 'mode/file',
          name: 'mode-file',
          component: () => import('../views/ModeRouter.vue'),
          props: { mode: 'file' }
        },
        {
          path: 'mode/kb',
          name: 'mode-kb',
          component: () => import('../views/ModeRouter.vue'),
          props: { mode: 'kb' }
        },
        {
          path: 'mode/analysis',
          name: 'mode-analysis',
          component: () => import('../views/ModeRouter.vue'),
          props: { mode: 'analysis' }
        },
        {
          path: 'knowledge/:id',
          name: 'knowledge-detail',
          component: () => import('../views/KnowledgeDetailView.vue')
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
