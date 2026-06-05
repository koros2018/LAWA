<script setup lang="ts">
import { ref, onMounted } from 'vue'

import api from '@/api'
import { t } from '@/i18n'

// t imported from @/i18n

const plan = ref<any>(null)
const loading = ref(true)
const tab = ref<'daily'|'weekly'>('daily')

onMounted(async () => {
  try {
    const res = await api.get('/plan/current')
    plan.value = res.data
  } catch { /* noop */ }
  finally { loading.value = false }
})
</script>

<template>
  <div class="view-container">
    <div v-if="loading">{{ t('loading') }}</div>
    <div v-else-if="plan">
      <h1>{{ t('plan') }}</h1>
      <div class="card plan-header">
        <div v-if="plan.overall_level">
          <span class="muted">{{ t('target_level') }}：</span>
          <strong>{{ plan.overall_level }}</strong>
        </div>
        <p v-if="plan.description" class="desc">{{ plan.description }}</p>
      </div>
      <div class="tabs">
        <button :class="{active:tab==='daily'}" @click="tab='daily'">{{ t('daily') }}</button>
        <button :class="{active:tab==='weekly'}" @click="tab='weekly'">{{ t('weekly') }}</button>
      </div>
      <template v-if="tab==='daily'">
        <div v-if="plan.daily_tasks?.length" class="task-list">
          <div v-for="(t,i) in plan.daily_tasks" :key="i" class="card task-card">
            <span class="chk">{{ t.completed?'✅':'⬜' }}</span>
            <div class="task-body">
              <h4>{{ t.title }}</h4>
              <p v-if="t.description" class="muted">{{ t.description }}</p>
              <div class="task-meta">
                <span class="tag">{{ t.type }}</span>
                <span class="reward">+{{ t.reward_coin||0 }}🪙</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty">{{ t('no_plan') }}</div>
      </template>
      <template v-else>
        <div v-if="plan.weekly_schedule" class="week-view">
          <div v-for="(desc,day) in plan.weekly_schedule" :key="day" class="card day-card">
            <h4>{{ day }}</h4><p>{{ desc }}</p>
          </div>
        </div>
        <div v-else class="empty">{{ t('no_plan') }}</div>
      </template>
    </div>
    <div v-else class="empty">
      <p>📋 {{ t('no_plan') }}</p>
      <router-link to="/assessment" class="btn-primary">{{ t('start_assessment') }}</router-link>
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 720px; margin: 0 auto; padding: 24px; }
.card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.plan-header { margin-bottom: 16px; } .desc { color: #666; font-size: .9rem; }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tabs button { padding: 8px 20px; border: 1px solid #ddd; border-radius: 8px; background: #fff; cursor: pointer; font-size: .9rem; }
.tabs button.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-card { display: flex; gap: 12px; align-items: flex-start; }
.chk { font-size: 1.2rem; } .task-body { flex:1; }
.task-body h4 { margin:0 0 4px } .task-body p { margin:0 0 8px }
.task-meta { display: flex; gap: 12px; font-size: .8rem; }
.tag { background: #eef2ff; color: var(--primary); padding: 2px 8px; border-radius: 4px; }
.reward { color: #f59e0b; }
.week-view { display: flex; flex-direction: column; gap: 8px; }
.day-card h4 { margin:0 0 4px } .day-card p { margin:0; color:#666; font-size:.9rem; }
.empty { text-align: center; padding: 60px 0; color: #888; }
.empty p { font-size: 1.2rem; margin-bottom: 20px; }
.muted { color:#888; }
.btn-primary { background:var(--primary); color:#fff; border:none; padding:12px 24px; border-radius:8px; cursor:pointer; text-decoration:none; display:inline-block; }
</style>
