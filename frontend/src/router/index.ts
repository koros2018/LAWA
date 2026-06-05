import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { guest: true } },
    { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { guest: true } },
    { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { requiresAuth: true } },
    { path: '/assessment', name: 'assessment', component: () => import('@/views/AssessmentView.vue'), meta: { requiresAuth: true } },
    { path: '/assessment/:id', name: 'assessment-result', component: () => import('@/views/AssessmentResultView.vue'), meta: { requiresAuth: true } },
    { path: '/tasks', name: 'tasks', component: () => import('@/views/TaskMarketView.vue'), meta: { requiresAuth: true } },
    { path: '/tasks/create', name: 'task-create', component: () => import('@/views/TaskCreateView.vue'), meta: { requiresAuth: true } },
    { path: '/tasks/:id', name: 'task-detail', component: () => import('@/views/TaskDetailView.vue'), meta: { requiresAuth: true } },
    { path: '/help', name: 'help', component: () => import('@/views/HelpView.vue'), meta: { requiresAuth: true } },
    { path: '/plan', name: 'plan', component: () => import('@/views/PlanView.vue'), meta: { requiresAuth: true } },
    { path: '/world', name: 'world', component: () => import('@/views/WorldMapView.vue'), meta: { requiresAuth: true } },
    { path: '/achievements', name: 'achievements', component: () => import('@/views/AchievementView.vue'), meta: { requiresAuth: true } },
    { path: '/events', name: 'events', component: () => import('@/views/EventsView.vue'), meta: { requiresAuth: true } },
    { path: '/shop', name: 'shop', component: () => import('@/views/ShopView.vue'), meta: { requiresAuth: true } },
    { path: '/coin', name: 'coin', component: () => import('@/views/CoinView.vue'), meta: { requiresAuth: true } },
    { path: '/guild', name: 'guild', component: () => import('@/views/GuildView.vue'), meta: { requiresAuth: true } },
    { path: '/leaderboard', name: 'leaderboard', component: () => import('@/views/LeaderboardView.vue'), meta: { requiresAuth: true } },
    { path: '/match', name: 'match', component: () => import('@/views/MatchView.vue'), meta: { requiresAuth: true } },
    { path: '/companion', name: 'companion', component: () => import('@/views/CompanionView.vue'), meta: { requiresAuth: true } },
    { path: '/vocabulary', name: 'vocabulary', component: () => import('@/views/VocabularyView.vue'), meta: { requiresAuth: true } },
    { path: '/tutor', name: 'tutor', component: () => import('@/views/TutorView.vue'), meta: { requiresAuth: true } },
    { path: '/llm-config', name: 'llm-config', component: () => import('@/views/LLMConfigView.vue'), meta: { requiresAuth: true } },
    { path: '/profile', name: 'profile', component: () => import('@/views/ProfileView.vue'), meta: { requiresAuth: true } },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue') },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('lawa_token')
  if (to.meta.requiresAuth && !token) return '/login'
  if (to.meta.guest && token) return '/dashboard'
  return true
})

export default router
