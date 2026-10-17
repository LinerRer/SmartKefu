import { createRouter, createWebHashHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

/**
 * 路由与全局守卫（v1.1）：
 * - meta.public：匿名可进（登录页、访客聊天窗）；
 * - meta.roles：进入该页所需角色，与后端 require_role 口径一致；
 * - 未登录访问受保护页 → 跳登录页并记录 redirect，登录后回原目标。
 */
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/kb' },
    {
      path: '/login',
      component: () => import('../views/Login.vue'),
      meta: { public: true },
    },
    {
      path: '/chat',
      component: () => import('../views/VisitorChat.vue'),
      meta: { public: true, title: '访客聊天窗' },
    },
    {
      path: '/',
      component: () => import('../layouts/AdminLayout.vue'),
      children: [
        {
          path: 'kb',
          component: () => import('../views/KbManage.vue'),
          meta: { roles: ['admin', 'agent'], title: '知识库管理' },
        },
        {
          path: 'agent',
          component: () => import('../views/AgentWorkbench.vue'),
          meta: { roles: ['admin', 'agent'], title: '坐席工作台' },
        },
        {
          path: 'dashboard',
          component: () => import('../views/Dashboard.vue'),
          meta: { roles: ['admin'], title: '数据看板' },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/kb' },
  ],
})

router.beforeEach((to) => {
  const userStore = useUserStore()
  const isLoggedIn = !!userStore.token

  if (to.meta.public) {
    // 已登录还去登录页 → 直接回主界面，避免重复登录
    if (to.path === '/login' && isLoggedIn) return '/kb'
    return true
  }

  if (!isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  const roles = (to.meta.roles as string[] | undefined) ?? []
  if (roles.length && !roles.includes(userStore.role)) {
    // 角色不足：回退到该角色菜单里的第一个页面
    return userStore.role === 'admin' ? '/kb' : '/agent'
  }
  return true
})

export default router
