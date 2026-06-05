<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/api'

interface EventTask {
  desc: string; type: string; target: number; xp: number; coins: number
}
interface CulturalEvent {
  id: string; code: string; name: string; emoji: string; description: string
  event_type: string; zone_code: string; start_date: string | null
  end_date: string | null; requirement_level: number; tasks: EventTask[]
  task_count: number; rewards: Record<string, any>
  is_expired: boolean; not_started: boolean; joined: boolean
  completed: boolean; completed_tasks: number[]
}

interface MyEvent {
  event_code: string; event_name: string; emoji: string; event_type: string
  task_index: number; task_progress: number; completed_tasks: number[]
  total_tasks: number; completed: boolean; completed_at: string | null
  progress_pct: number; rewards: Record<string, any>
}

const userId = ref('')
const events = ref<CulturalEvent[]>([])
const myEvents = ref<MyEvent[]>([])
const filter = ref('all')
const tab = ref<'all' | 'mine'>('all')
const message = ref('')

const typeLabels: Record<string, string> = {
  festival: '🎊 文化节日', limited_dungeon: '⚔️ 限时副本', challenge: '🏆 挑战赛',
}
const typeColors: Record<string, string> = {
  festival: '#ff6b6b', limited_dungeon: '#7c3aed', challenge: '#f59e0b',
}
const taskTypeIcons: Record<string, string> = {
  speak: '🎤', write: '✍️', read: '📖', translate: '🔄', listen: '👂',
}

const filtered = computed(() => {
  if (filter.value === 'all') return events.value
  return events.value.filter(e => e.event_type === filter.value)
})

onMounted(async () => {
  const u = JSON.parse(localStorage.getItem('lawa_user') || '{}')
  userId.value = u.id || ''
  await Promise.all([refreshAll(), refreshMy()])
})

async function refreshAll() {
  try {
    const { data } = await api.get(`/rpg/events?user_id=${userId.value}`)
    events.value = data.events
  } catch {}
}
async function refreshMy() {
  try {
    const { data } = await api.get(`/rpg/events/my?user_id=${userId.value}`)
    myEvents.value = data.events
  } catch {}
}

async function joinEvent(code: string) {
  try {
    const { data } = await api.post('/rpg/events/join', { user_id: userId.value, code })
    message.value = data.message || `已参与 ${code}`
    await Promise.all([refreshAll(), refreshMy()])
  } catch (e: any) {
    message.value = e.response?.data?.detail || '参与失败'
  }
}

async function submitProgress(code: string, taskIndex: number) {
  try {
    const { data } = await api.post('/rpg/events/progress', {
      user_id: userId.value, code, task_index: taskIndex, value: 1,
    })
    if (data.task_completed) {
      message.value = `✅ 任务完成！+${data.xp_earned}XP +${data.coins_earned}金币`
    }
    if (data.event_completed) {
      message.value = `🎉 活动全部完成！奖励：+${data.final_rewards?.xp || 0}XP +${data.final_rewards?.coins || 0}金币`
    }
    await Promise.all([refreshAll(), refreshMy()])
  } catch (e: any) {
    message.value = e.response?.data?.detail || '提交失败'
  }
}
</script>

<template>
  <div class="events-page">
    <h1>🎭 文化活动</h1>
    <p v-if="message" class="msg">{{ message }}</p>

    <!-- Tab 切换 -->
    <div class="tabs">
      <button :class="{ active: tab === 'all' }" @click="tab = 'all'">📋 全部活动</button>
      <button :class="{ active: tab === 'mine' }" @click="tab = 'mine'">📌 我的活动</button>
    </div>

    <!-- 全部活动 -->
    <div v-if="tab === 'all'">
      <div class="filter-bar">
        <button
          v-for="(label, key) in { all: '全部', festival: '文化节日', limited_dungeon: '限时副本', challenge: '挑战赛' }"
          :key="key"
          :class="{ active: filter === key }"
          @click="filter = key"
        >{{ label }}</button>
      </div>
      <div class="event-grid">
        <div
          v-for="e in filtered" :key="e.code"
          class="event-card"
          :class="{ completed: e.completed, expired: e.is_expired }"
        >
          <div class="card-header">
            <span class="emoji">{{ e.emoji }}</span>
            <div class="header-info">
              <span class="name">{{ e.name }}</span>
              <span
                class="type-badge"
                :style="{ background: typeColors[e.event_type] }"
              >{{ typeLabels[e.event_type]?.slice(2) || e.event_type }}</span>
            </div>
          </div>
          <p class="desc">{{ e.description }}</p>
          <div class="meta">
            <span>📊 等级 {{ e.requirement_level }}+</span>
            <span>📝 {{ e.task_count }} 个任务</span>
            <span v-if="e.is_expired">⏰ 已过期</span>
            <span v-else-if="e.not_started">🔒 未开始</span>
          </div>

          <!-- 任务列表 -->
          <ul class="task-list">
            <li
              v-for="(t, i) in e.tasks"
              :key="i"
              :class="{ done: e.completed_tasks.includes(i) }"
            >
              <span class="task-icon">{{ taskTypeIcons[t.type] || '📌' }}</span>
              {{ t.desc }}
              <span class="task-reward">+{{ t.xp }}XP +{{ t.coins }}🪙</span>
            </li>
          </ul>

          <!-- 奖励 -->
          <div class="rewards">
            🎁 完成奖励：+{{ e.rewards?.xp || 0 }}XP +{{ e.rewards?.coins || 0 }}🪙
          </div>

          <!-- 按钮 -->
          <div class="actions">
            <button v-if="e.completed" class="btn-done" disabled>✅ 已完成</button>
            <button v-else-if="e.joined" class="btn-progress" @click="submitProgress(e.code, 0)">
              📤 提交进度
            </button>
            <button
              v-else-if="!e.is_expired && !e.not_started"
              class="btn-join"
              @click="joinEvent(e.code)"
            >
              🚀 参与活动
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 我的活动 -->
    <div v-if="tab === 'mine'" class="my-section">
      <div v-if="myEvents.length === 0" class="empty">还没有参与任何活动 🎈</div>
      <div v-for="me in myEvents" :key="me.event_code" class="my-card" :class="{ done: me.completed }">
        <div class="my-header">
          <span class="emoji">{{ me.emoji }}</span>
          <span class="name">{{ me.event_name }}</span>
          <span class="type-badge" :style="{ background: typeColors[me.event_type] }">
            {{ typeLabels[me.event_type]?.slice(2) || me.event_type }}
          </span>
        </div>
        <!-- 进度条 -->
        <div class="progress-bar">
          <div class="fill" :style="{ width: me.progress_pct + '%' }"></div>
          <span class="pct">{{ me.progress_pct }}%</span>
        </div>
        <div class="my-meta">
          {{ me.completed_tasks.length }}/{{ me.total_tasks }} 任务完成
          <span v-if="me.completed"> · 🎉 已全部完成</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.events-page { max-width: 960px; margin: 0 auto; padding: 24px 16px 80px; }
h1 { font-size: 1.6rem; margin-bottom: 16px; }
.msg { background: #e8f5e9; color: #2e7d32; padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; }

.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
.tabs button {
  padding: 8px 20px; border: 1px solid #ddd; background: #fff; border-radius: 20px;
  cursor: pointer; font-size: .9rem; transition: all .2s;
}
.tabs button.active { background: #1976d2; color: #fff; border-color: #1976d2; }

.filter-bar { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.filter-bar button {
  padding: 6px 14px; border: 1px solid #e0e0e0; border-radius: 16px;
  background: #f5f5f5; cursor: pointer; font-size: .85rem;
}
.filter-bar button.active { background: #1976d2; color: #fff; border-color: #1976d2; }

.event-grid { display: grid; gap: 20px; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); }

.event-card {
  background: #fff; border-radius: 12px; padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,.08); transition: transform .2s;
}
.event-card:hover { transform: translateY(-2px); }
.event-card.completed { opacity: .7; }
.event-card.expired { opacity: .5; }

.card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.card-header .emoji { font-size: 2rem; }
.header-info { display: flex; flex-direction: column; gap: 4px; }
.header-info .name { font-weight: 600; font-size: 1.05rem; }
.type-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; color: #fff; font-size: .75rem; }

.desc { color: #666; font-size: .88rem; margin-bottom: 10px; line-height: 1.5; }

.meta { display: flex; gap: 12px; font-size: .82rem; color: #888; margin-bottom: 12px; }

.task-list { list-style: none; padding: 0; margin: 0 0 12px; }
.task-list li {
  padding: 6px 10px; border-radius: 6px; background: #f8f9fa; margin-bottom: 6px;
  font-size: .85rem; display: flex; align-items: center; gap: 6px;
}
.task-list li.done { background: #e8f5e9; text-decoration: line-through; color: #999; }
.task-icon { font-size: 1rem; }
.task-reward { margin-left: auto; color: #1976d2; font-size: .78rem; white-space: nowrap; }

.rewards { font-size: .85rem; color: #f59e0b; margin-bottom: 12px; }

.actions { display: flex; gap: 8px; }
.btn-join { background: #1976d2; color: #fff; border: none; padding: 8px 18px; border-radius: 8px; cursor: pointer; font-size: .9rem; }
.btn-progress { background: #43a047; color: #fff; border: none; padding: 8px 18px; border-radius: 8px; cursor: pointer; font-size: .9rem; }
.btn-done { background: #e0e0e0; color: #999; border: none; padding: 8px 18px; border-radius: 8px; font-size: .9rem; }

.my-section { display: flex; flex-direction: column; gap: 12px; }
.empty { text-align: center; color: #999; padding: 40px 0; font-size: 1.1rem; }
.my-card {
  background: #fff; border-radius: 10px; padding: 16px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}
.my-card.done { background: #f1f8e9; }
.my-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.my-header .emoji { font-size: 1.5rem; }
.my-header .name { font-weight: 600; }

.progress-bar {
  height: 10px; background: #e0e0e0; border-radius: 5px; position: relative;
  margin-bottom: 6px; overflow: hidden;
}
.progress-bar .fill { height: 100%; background: linear-gradient(90deg, #43a047, #66bb6a); border-radius: 5px; transition: width .5s; }
.progress-bar .pct { position: absolute; right: 4px; top: -18px; font-size: .75rem; color: #666; }

.my-meta { font-size: .85rem; color: #888; }
</style>
