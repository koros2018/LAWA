<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'

import api from '@/api'
import { t } from '@/i18n'

// t imported from @/i18n

const router = useRouter()
const tasks = ref<any[]>([])
const loading = ref(true)
const page = ref(1)
const totalPages = ref(1)
const filterStatus = ref('')
const filterType = ref('')
const user = ref<any>({})

const taskTypes = ['translation', 'proofreading', 'summary', 'writing', 'speaking', 'tutoring', 'other']
const statuses = ['open', 'assigned', 'submitted', 'completed']

onMounted(async () => {
  const u = localStorage.getItem('lawa_user')
  if (u) user.value = JSON.parse(u)
  await load()
})

async function load() {
  loading.value = true
  try {
    const params: any = { page: page.value, limit: 20 }
    if (filterStatus.value) params.status = filterStatus.value
    if (filterType.value) params.task_type = filterType.value
    if (user.value.id) params.user_id = user.value.id
    const res = await api.get('/tasks', { params })
    tasks.value = res.data.tasks || []
    totalPages.value = res.data.total_pages || 1
  } catch { tasks.value = [] }
  finally { loading.value = false }
}

watch(page, load)

function typeLabel(t: string) {
  const m: Record<string,string> = { translation:'翻译', proofreading:'润色', summary:'摘要', writing:'写作', speaking:'口语', tutoring:'辅导', other:'其他' }
  return m[t] || t
}

function statusBadge(s: string) {
  const m: Record<string,{label:string,cls:string}> = { open: {label:'待接单', cls:'open'}, assigned: {label:'已接单', cls:'assigned'}, submitted: {label:'待验收', cls:'submitted'}, completed: {label:'已完成', cls:'completed'}, cancelled: {label:'已取消', cls:'cancelled'} }
  return m[s] || {label:s, cls:''}
}

function timeAgo(ts: string) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = Date.now()
  const diff = Math.floor((now - d.getTime()) / 1000)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff/60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff/3600)}小时前`
  return d.toLocaleDateString()
}
</script>

<template>
  <div class="view-container">
    <div class="header-row">
      <h1>{{ t('tasks') }}</h1>
      <router-link to="/tasks/create" class="btn-primary">＋ {{ t('publish_task') }}</router-link>
    </div>

    <div class="filters">
      <select v-model="filterStatus" @change="page=1;load()">
        <option value="">{{ t('all_status') }}</option>
        <option v-for="s in statuses" :key="s" :value="s">{{ statusBadge(s).label }}</option>
      </select>
      <select v-model="filterType" @change="page=1;load()">
        <option value="">{{ t('all_types') }}</option>
        <option v-for="t in taskTypes" :key="t" :value="t">{{ typeLabel(t) }}</option>
      </select>
    </div>

    <div v-if="loading" class="loading">{{ t('loading') }}</div>
    <div v-else-if="tasks.length === 0" class="empty">
      <p>📋 {{ t('no_tasks_yet') }}</p>
    </div>
    <div v-else class="task-list">
      <div v-for="task in tasks" :key="task.id" class="task-card" @click="router.push(`/tasks/${task.id}`)">
        <div class="task-header">
          <span :class="['status-badge', statusBadge(task.status).cls]">{{ statusBadge(task.status).label }}</span>
          <span class="task-type">{{ typeLabel(task.task_type) }}</span>
          <span class="reward">🪙 {{ task.reward_coin || 0 }}</span>
        </div>
        <h3>{{ task.title }}</h3>
        <p v-if="task.description" class="desc">{{ task.description.slice(0, 100) }}{{ task.description.length > 100 ? '...' : '' }}</p>
        <div class="task-footer">
          <span class="publisher">{{ task.publisher_name || task.publisher_id?.slice(0, 8) || '匿名' }}</span>
          <span class="time">{{ timeAgo(task.created_at) }}</span>
        </div>
      </div>
    </div>

    <div v-if="totalPages > 1" class="pagination">
      <button @click="page--" :disabled="page <= 1">{{ t('prev') }}</button>
      <span>{{ page }}/{{ totalPages }}</span>
      <button @click="page++" :disabled="page >= totalPages">{{ t('next') }}</button>
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 800px; margin: 0 auto; padding: 24px; }
.header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.header-row h1 { margin: 0; }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-size: .9rem; }
.filters { display: flex; gap: 8px; margin-bottom: 16px; }
.filters select { padding: 8px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: .9rem; background: white; }
.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,.08); cursor: pointer; transition: transform .15s; }
.task-card:hover { transform: translateY(-2px); }
.task-header { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.status-badge { padding: 2px 10px; border-radius: 12px; font-size: .75rem; font-weight: 600; }
.status-badge.open { background: #dbeafe; color: #1e40af; }
.status-badge.assigned { background: #fef3c7; color: #92400e; }
.status-badge.submitted { background: #e0e7ff; color: #3730a3; }
.status-badge.completed { background: #d1fae5; color: #065f46; }
.task-type { color: #666; font-size: .8rem; }
.reward { margin-left: auto; font-weight: 600; color: #f59e0b; }
h3 { margin: 0 0 4px; font-size: 1.05rem; }
.desc { color: #666; font-size: .85rem; margin: 0 0 8px; }
.task-footer { display: flex; justify-content: space-between; font-size: .8rem; color: #999; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 20px; }
.pagination button { padding: 6px 16px; border: 1px solid #ddd; border-radius: 6px; background: white; cursor: pointer; }
.pagination button:disabled { opacity: .5; cursor: not-allowed; }
.loading { text-align: center; padding: 40px; color: #888; }
.empty { text-align: center; padding: 60px; color: #888; }
</style>
