<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/api'

interface Achievement {
  id: string; code: string; name: string; emoji: string; description: string
  category: string; tier: number; xp_reward: number; coin_reward: number
  requirement_desc: string; progress: number; completed: boolean; hidden: boolean
}
interface Badge {
  code: string; name: string; emoji: string; from_achievement: string
}

const userId = ref('')
const achievements = ref<Achievement[]>([])
const badges = ref<Badge[]>([])
const filter = ref('all')
const message = ref('')

const catLabels: Record<string,string> = { all:'全部', milestone:'里程碑', challenge:'挑战', social:'社交', collection:'收藏' }

const filtered = computed(() => {
  if (filter.value === 'all') return achievements.value
  return achievements.value.filter(a => a.category === filter.value)
})
const completedCount = computed(() => achievements.value.filter(a => a.completed).length)

onMounted(async () => {
  const u = JSON.parse(localStorage.getItem('lawa_user') || '{}')
  userId.value = u.id || ''
  await Promise.all([refreshAch(), refreshBadges()])
})

async function refreshAch() {
  try {
    const { data } = await api.get(`/rpg/achievements?user_id=${userId.value}`)
    achievements.value = data.achievements
  } catch {}
}
async function refreshBadges() {
  try {
    const { data } = await api.get(`/rpg/badges?user_id=${userId.value}`)
    badges.value = data.badges
  } catch {}
}
async function checkUnlock() {
  try {
    const { data } = await api.post('/rpg/achievements/check', { user_id: userId.value })
    if (data.count > 0) {
      message.value = `🎉 解锁了 ${data.newly_unlocked.map((u:any) => u.emoji+u.name).join(', ')}`
      await refreshAch()
      await refreshBadges()
    } else {
      message.value = '暂无新成就可解锁'
    }
  } catch (e: any) {
    message.value = e.response?.data?.detail || '检查失败'
  }
}

const tierDots = (n: number) => '⭐'.repeat(n)
</script>

<template>
  <div class="ach-page">
    <h2>🏆 成就殿堂</h2>

    <!-- 统计栏 -->
    <div class="stats-bar">
      <span>{{ completedCount }}/{{ achievements.length }} 已完成</span>
      <span v-if="badges.length">| 🏅 {{ badges.length }} 徽章</span>
      <button @click="checkUnlock" class="btn-check">🔍 检查解锁</button>
    </div>
    <p v-if="message" class="msg">{{ message }}</p>

    <!-- 徽章 -->
    <div v-if="badges.length" class="badges">
      <h4>🏅 已获徽章</h4>
      <div class="badge-row">
        <span v-for="b in badges" :key="b.code" class="badge-item" :title="b.from_achievement">
          {{ b.emoji }} {{ b.name }}
        </span>
      </div>
    </div>

    <!-- 分类筛选 -->
    <div class="filters">
      <button v-for="(label, key) in catLabels" :key="key"
        :class="{active: filter===key}" @click="filter=key">{{ label }}</button>
    </div>

    <!-- 成就列表 -->
    <div class="ach-grid">
      <div v-for="a in filtered" :key="a.id" class="ach-card" :class="{completed:a.completed}">
        <div class="ach-header">
          <span class="ach-emoji">{{ a.emoji }}</span>
          <span class="ach-name">{{ a.name }}</span>
          <span class="ach-tier">{{ tierDots(a.tier) }}</span>
        </div>
        <div class="ach-desc">{{ a.description }}</div>
        <div class="ach-req">{{ a.requirement_desc }}</div>
        <div class="ach-progress-bar">
          <div class="ach-fill" :style="{width:Math.min(100, (a.progress||0)/5*100)+'%'}"></div>
          <span class="ach-progress-text">{{ a.progress || 0 }}/5</span>
        </div>
        <div class="ach-rewards">🎁 {{ a.xp_reward }}XP · {{ a.coin_reward }}🪙</div>
        <div v-if="a.completed" class="ach-done">✅ 已达成</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ach-page { padding: 16px; max-width: 900px; margin: 0 auto; }
.stats-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; font-size: 0.9rem; color: #6b7280; }
.btn-check { padding: 6px 14px; background: #8b5cf6; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 0.85rem; }
.msg { color: #22c55e; font-size: 0.85rem; margin: 0 0 12px; }
.badges { margin-bottom: 16px; }
.badges h4 { margin: 0 0 8px; }
.badge-row { display: flex; gap: 12px; flex-wrap: wrap; }
.badge-item { background: #fef3c7; padding: 6px 12px; border-radius: 20px; font-size: 0.9rem; }
.filters { display: flex; gap: 8px; margin-bottom: 16px; }
.filters button { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 20px; background: white; cursor: pointer; font-size: 0.85rem; }
.filters button.active { background: #8b5cf6; color: white; border-color: #8b5cf6; }
.ach-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.ach-card { background: white; border-radius: 12px; padding: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); transition: all 0.2s; }
.ach-card.completed { background: #f0fdf4; border: 1px solid #bbf7d0; }
.ach-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.ach-emoji { font-size: 1.4rem; } .ach-name { font-weight: 600; flex:1; }
.ach-tier { font-size: 0.7rem; } .ach-desc { font-size: 0.8rem; color: #6b7280; margin-bottom: 4px; }
.ach-req { font-size: 0.75rem; color: #9ca3af; margin-bottom: 6px; }
.ach-progress-bar { height: 6px; background: #e5e7eb; border-radius: 3px; position: relative; margin-bottom: 4px; }
.ach-fill { height: 100%; background: #8b5cf6; border-radius: 3px; transition: width 0.3s; }
.ach-completed .ach-fill { background: #22c55e; }
.ach-progress-text { position: absolute; right: 0; top: -18px; font-size: 0.7rem; color: #9ca3af; }
.ach-rewards { font-size: 0.75rem; color: #f59e0b; margin-bottom: 4px; }
.ach-done { font-size: 0.8rem; color: #22c55e; font-weight: 600; }
</style>
