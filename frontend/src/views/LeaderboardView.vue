<script setup lang="ts">
import { ref, onMounted } from 'vue'

import api from '@/api'
import { t } from '@/i18n'

// t imported from @/i18n

const boardType = ref('coins')
const period = ref('daily')
const entries = ref<any[]>([])
const userRank = ref<any>(null)
const loading = ref(true)
const user = ref<any>({})

const periods = ['daily', 'weekly', 'all']
const types = ['coins', 'study_time', 'help_count', 'tasks_completed']
const typeLabels: Record<string,string> = { coins: t('board_coins'), study_time: t('board_study'), help_count: t('board_help'), tasks_completed: t('board_tasks') }
const periodLabels: Record<string,string> = { daily: t('period_daily'), weekly: t('period_weekly'), all: t('period_all') }

onMounted(async () => {
  const u = localStorage.getItem('lawa_user')
  if (u) user.value = JSON.parse(u)
  await load()
})

async function load() {
  loading.value = true
  try {
    const params: any = { period: period.value, limit: 20 }
    if (user.value.id) params.user_id = user.value.id
    const res = await api.get(`/community/leaderboard/${boardType.value}`, { params })
    entries.value = res.data.entries || []
    userRank.value = res.data.user_rank || null
  } catch { entries.value = [] }
  finally { loading.value = false }
}
</script>

<template>
  <div class="view-container">
    <h1>{{ t('leaderboard') }}</h1>
    <div class="filters">
      <div class="filter-group">
        <button v-for="tp in types" :key="tp" :class="{active:boardType===tp}" @click="boardType=tp;load()">{{ typeLabels[tp] }}</button>
      </div>
      <div class="filter-group">
        <button v-for="p in periods" :key="p" :class="{active:period===p}" @click="period=p;load()">{{ periodLabels[p] }}</button>
      </div>
    </div>
    <div v-if="userRank" class="my-rank">
      <span>🏆 {{ t('your_rank') }}: #{{ userRank.rank }} / {{ userRank.total }}</span>
      <span class="score">{{ userRank.score?.toFixed(0) || 0 }} 分</span>
    </div>
    <div v-if="loading">{{ t('loading') }}</div>
    <div v-else-if="entries.length===0" class="empty">{{ t('no_data') }}</div>
    <div v-else class="rank-list">
      <div v-for="e in entries" :key="e.user_id" :class="['rank-item', e.rank<=3?'top':'']">
        <span class="num">{{ e.rank<=3?['🥇','🥈','🥉'][e.rank-1]:`#${e.rank}` }}</span>
        <span class="name">{{ e.user_id?.slice(0,8)||'匿名' }}</span>
        <span class="score">{{ e.score?.toFixed(0)||0 }} 分</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 720px; margin:0 auto; padding:24px; }
.filters { display:flex; flex-direction:column; gap:8px; margin-bottom:16px; }
.filter-group { display:flex; gap:6px; flex-wrap:wrap; }
.filter-group button { padding:6px 16px; border:1px solid #ddd; border-radius:20px; background:white; cursor:pointer; font-size:.85rem; }
.filter-group button.active { background:var(--primary); color:white; border-color:var(--primary); }
.my-rank { display:flex; justify-content:space-between; padding:12px 16px; background:#fffbeb; border:1px solid #fde68a; border-radius:8px; margin-bottom:16px; font-size:.9rem; }
.my-rank .score { font-weight:700; }
.rank-list { display:flex; flex-direction:column; gap:4px; }
.rank-item { display:flex; align-items:center; gap:12px; padding:12px 16px; background:white; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.06); }
.rank-item.top { background:#fffbe6; }
.num { font-size:1.1rem; width:36px; text-align:center; }
.name { flex:1; font-size:.9rem; }
.score { font-weight:700; color:var(--primary); }
.empty { text-align:center; padding:60px; color:#888; }
</style>
