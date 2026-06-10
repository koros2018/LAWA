<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import TutorChatWidget from '@/components/TutorChatWidget.vue'

const router = useRouter()
const route = useRoute()
const isAuth = computed(() => !!localStorage.getItem('lawa_token'))
const user = computed(() => {
  try { return JSON.parse(localStorage.getItem('lawa_user') || 'null') }
  catch { return null }
})

// 面包屑：根据当前路径生成
const breadcrumbs = computed(() => {
  const path = route.path
  const crumbs: { label: string; to: string }[] = [
    { label: '🏠 主页', to: '/dashboard' },
  ]
  if (path.startsWith('/assessment')) crumbs.push({ label: '📝 评估', to: '/assessment' })
  else if (path.startsWith('/tasks')) crumbs.push({ label: '📋 任务', to: '/tasks' })
  else if (path.startsWith('/world')) crumbs.push({ label: '🌍 世界地图', to: '/world' })
  else if (path.startsWith('/tutor')) crumbs.push({ label: '🧙 导师', to: '/tutor' })
  else if (path.startsWith('/guild')) crumbs.push({ label: '⚔️ 公会', to: '/guild' })
  else if (path.startsWith('/shop')) crumbs.push({ label: '🏪 商店', to: '/shop' })
  else if (path.startsWith('/llm-config')) crumbs.push({ label: '🤖 LLM配置', to: '/llm-config' })
  else if (path.startsWith('/achievements')) crumbs.push({ label: '🏆 成就', to: '/achievements' })
  else if (path.startsWith('/events')) crumbs.push({ label: '🎉 活动', to: '/events' })
  else if (path.startsWith('/leaderboard')) crumbs.push({ label: '🏅 排行', to: '/leaderboard' })
  else if (path.startsWith('/profile')) crumbs.push({ label: '👤 画像', to: '/profile' })
  return crumbs
})

function logout() {
  localStorage.removeItem('lawa_token')
  localStorage.removeItem('lawa_user')
  router.push('/login')
}
</script>

<template>
  <div id="app-shell">
    <aside v-if="isAuth" class="sidebar">
      <div class="sidebar-header">
        <router-link to="/dashboard" class="logo">🦝 LAWA</router-link>
      </div>
      <nav class="sidebar-nav">
        <div class="nav-group-label">📊 概览</div>
        <router-link to="/dashboard" class="nav-item"><span>📊</span> <span>Dashboard</span></router-link>
        <router-link to="/profile" class="nav-item"><span>👤</span> <span>画像</span></router-link>
        <router-link to="/leaderboard" class="nav-item"><span>🏅</span> <span>排行</span></router-link>

        <div class="nav-group-label">🎮 游戏</div>
        <router-link to="/world" class="nav-item"><span>🌍</span> <span>世界地图</span></router-link>
        <router-link to="/shop" class="nav-item"><span>🏪</span> <span>商店</span></router-link>
        <router-link to="/achievements" class="nav-item"><span>🏆</span> <span>成就</span></router-link>
        <router-link to="/events" class="nav-item"><span>🎉</span> <span>活动</span></router-link>
        <router-link to="/guild" class="nav-item"><span>⚔️</span> <span>公会</span></router-link>

        <div class="nav-group-label">📝 学习</div>
        <router-link to="/assessment" class="nav-item"><span>📝</span> <span>评估</span></router-link>
        <router-link to="/tasks" class="nav-item"><span>📋</span> <span>任务</span></router-link>
        <router-link to="/tutor" class="nav-item"><span>🧙</span> <span>导师</span></router-link>
        <router-link to="/match" class="nav-item"><span>🤝</span> <span>匹配</span></router-link>
        <router-link to="/companion" class="nav-item"><span>👥</span> <span>学伴</span></router-link>
        <router-link to="/plan" class="nav-item"><span>📅</span> <span>学习计划</span></router-link>

        <div class="nav-group-label">⚙️ 设置</div>
        <router-link to="/llm-config" class="nav-item"><span>🤖</span> <span>LLM</span></router-link>
      </nav>
      <div class="sidebar-footer" v-if="user">
        <div class="user-info">
          <span class="user-avatar">👤</span>
          <span class="user-name">{{ user.username }}</span>
        </div>
        <button class="logout-btn" @click="logout" title="退出登录">
          🚪 <span>退出</span>
        </button>
      </div>
    </aside>
    <main :class="{ 'full-width': !isAuth }">
      <!-- 面包屑导航 -->
      <nav v-if="isAuth && breadcrumbs.length > 1" class="breadcrumb">
        <span v-for="(c, i) in breadcrumbs" :key="c.to">
          <router-link :to="c.to" class="bc-link">{{ c.label }}</router-link>
          <span v-if="i < breadcrumbs.length - 1" class="bc-sep">›</span>
        </span>
      </nav>
      <router-view />
      <TutorChatWidget v-if="isAuth" />
    </main>
  </div>
</template>

<style>
:root { --primary: #667eea; --sidebar-width: 200px; --bg: #f5f7fa; }
* { box-sizing: border-box; margin: 0; }
body { font-family: -apple-system, sans-serif; background: #f5f7fa; color: #333; min-height: 100vh; }
#app { min-height: 100vh; }
#app-shell { min-height: 100vh; display: flex; }
.sidebar { width: var(--sidebar-width); background: white; height: 100vh; position: fixed; border-right: 1px solid #e9ecef; display: flex; flex-direction: column; padding: 16px; z-index: 10; }
.sidebar-header { padding: 8px 0 16px; border-bottom: 1px solid #f0f0f0; margin-bottom: 8px; }
.sidebar-header .logo { font-size: 1.2rem; font-weight: 700; color: var(--primary); text-decoration: none; }
.sidebar-nav { flex: 1; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 10px 8px; border-radius: 8px; color: #555; text-decoration: none; font-size: 0.9rem; transition: background 0.2s; margin-bottom: 4px; }
.nav-item:hover, .nav-item.router-link-active { background: #f0f0ff; color: var(--primary); }
.nav-group-label { font-size: 0.7rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.5px; padding: 12px 8px 4px; font-weight: 600; }
.sidebar-footer { padding: 12px 0 0; border-top: 1px solid #f0f0f0; display: flex; flex-direction: column; gap: 8px; }
.user-info { display: flex; align-items: center; gap: 6px; font-size: 0.85rem; }
.user-avatar { font-size: 1.1rem; }
.user-name { font-weight: 500; color: #333; }
.logout-btn { display: flex; align-items: center; gap: 4px; padding: 6px 10px; border: 1px solid #fecaca; border-radius: 6px; background: #fef2f2; color: #dc2626; cursor: pointer; font-size: 0.8rem; transition: all .15s; }
.logout-btn:hover { background: #fee2e2; border-color: #f87171; }
main { flex: 1; margin-left: var(--sidebar-width); min-height: 100vh; }
main.full-width { margin-left: 0; }
/* 面包屑 */
.breadcrumb { padding: 10px 24px; font-size: .85rem; background: #fafbfc; border-bottom: 1px solid #f0f0f0; }
.bc-link { color: #667eea; text-decoration: none; }
.bc-link:hover { text-decoration: underline; }
.bc-sep { margin: 0 6px; color: #ccc; }
</style>
