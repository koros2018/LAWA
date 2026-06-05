<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

import api from '@/api'
import { t } from '@/i18n'

// t imported from @/i18n

const balance = ref(0)
const transactions = ref<any[]>([])
const loading = ref(true)
const page = ref(1)
const totalPages = ref(1)
const stats = ref({ daily: 0, weekly: 0 })

async function load() {
  try {
    const [txRes, stRes] = await Promise.all([
      api.get(`/coin/transactions?page=${page.value}&limit=20`),
      api.get('/coin/stats'),
    ])
    const d = txRes.data
    transactions.value = d.transactions || d.items || d
    totalPages.value = d.total_pages || 1
    balance.value = d.balance || 0
    stats.value = stRes.data
  } catch { /* noop */ }
  finally { loading.value = false }
}
onMounted(load)
watch(page, load)

function typeIcon(type: string) {
  const m: Record<string,string> = { earn:'🪙', spend:'💸', daily_login:'🎁', daily_task:'📋', referral:'🤝', transfer:'🔄', companion:'💬', assessment:'📝', penalty:'⚠️' }
  return m[type]||'🪙'
}
</script>

<template>
  <div class="view-container">
    <h1>{{ t('coins') }}</h1>
    <div class="card balance-card">
      <div class="bl">{{ t('balance') }}</div>
      <div class="bv">{{ balance }}</div>
      <div class="bs"><span>{{ t('today') }}：+{{ stats.daily||0 }}</span><span>{{ t('week') }}：+{{ stats.weekly||0 }}</span></div>
    </div>
    <div class="quick-links">
      <router-link to="/companion" class="ql-btn">💬 {{ t('companion') }}</router-link>
      <router-link to="/assessment" class="ql-btn">📝 {{ t('assessment') }}</router-link>
      <router-link to="/tasks" class="ql-btn">📋 {{ t('tasks') }}</router-link>
    </div>
    <div v-if="loading">{{ t('loading') }}</div>
    <div v-else class="card tx-list">
      <h3>{{ t('transaction_history') }}</h3>
      <div v-for="tx in transactions" :key="tx.id" class="tx-item">
        <span class="tx-icon">{{ typeIcon(tx.type) }}</span>
        <div class="tx-info">
          <span class="tx-type">{{ tx.type }}</span>
          <span v-if="tx.created_at" class="tx-time">{{ new Date(tx.created_at).toLocaleDateString() }}</span>
        </div>
        <span :class="['tx-amt', (tx.amount||0)>0?'pos':'neg']">{{ (tx.amount||0)>0?'+':'' }}{{ tx.amount||0 }}</span>
      </div>
      <div v-if="transactions.length===0" class="empty">{{ t('no_transactions') }}</div>
    </div>
    <div v-if="totalPages>1" class="pagination">
      <button @click="page--" :disabled="page<=1">{{ t('prev') }}</button>
      <span>{{ page }}/{{ totalPages }}</span>
      <button @click="page++" :disabled="page>=totalPages">{{ t('next') }}</button>
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 720px; margin: 0 auto; padding: 24px; }
.card { background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.balance-card { text-align: center; margin-bottom: 20px; }
.bl { font-size: .85rem; color: #888; }
.bv { font-size: 3rem; font-weight: 700; color: #f59e0b; margin: 8px 0; }
.bs { display: flex; justify-content: center; gap: 24px; font-size: .85rem; color: #888; }
.quick-links { display: flex; gap: 8px; margin-bottom: 20px; }
.ql-btn { flex:1; text-align:center; padding:12px; background:#fffbeb; border:1px solid #fde68a; border-radius:8px; text-decoration:none; color:#92400e; font-size:.85rem; }
.tx-list { margin-bottom: 20px; }
.tx-list h3 { margin: 0 0 12px; }
.tx-item { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid #f0f0f0; }
.tx-icon { font-size: 1.2rem; }
.tx-info { flex: 1; }
.tx-type { display: block; font-size: .9rem; }
.tx-time { font-size: .75rem; color: #aaa; }
.tx-amt { font-weight: 700; font-size: 1rem; }
.pos { color: #16a34a; } .neg { color: #dc2626; }
.empty { text-align: center; padding: 20px; color: #888; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 12px; }
.pagination button { padding: 6px 16px; border: 1px solid #ddd; border-radius: 6px; background: #fff; cursor: pointer; }
.pagination button:disabled { opacity: .5; }
</style>
