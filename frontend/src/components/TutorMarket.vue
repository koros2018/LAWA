<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'

const props = defineProps<{ lang: string; userId: string }>()

const loadMarket = ref(false)
const marketTutors = ref<any[]>([])
const marketPage = ref(1)

onMounted(() => doMarket())

const styleLabel = (s: string): string => {
  const m: Record<string,string> = { patient_explainer:'耐心讲解', drill_master:'训练大师', conversationalist:'对话达人', storyteller:'故事大王', grammar_nerd:'语法专精', coach:'教练型' }
  return m[s] || s
}

async function doMarket() {
  loadMarket.value = true
  try {
    const res = await api.get('/tutor/market', { params: { lang: props.lang, page: marketPage.value, limit: 10 } })
    marketTutors.value = res.data.tutors || []
  } catch { /* ignore */ } finally { loadMarket.value = false }
}

async function doRent(tutor: any) {
  try {
    await api.post('/tutor/rent', { user_id: props.userId, tutor_id: tutor.tutor_id })
    alert('Rented!')
  } catch { /* ignore */ }
}

defineExpose({ doMarket })
</script>

<template>
  <div class="card">
    <button @click="doMarket" :disabled="loadMarket" class="btn-primary btn-block" style="margin-bottom:16px">
      {{ loadMarket ? '🏪 ...' : '🏪 Browse Tutor Market' }}
    </button>
    <div v-if="marketTutors.length === 0 && !loadMarket" class="empty">No tutors in the market yet.</div>
    <div v-for="t in marketTutors" :key="t.tutor_id" class="market-card">
      <div class="mh">
        <div><strong>{{ t.tutor_name }}</strong> <span class="style-badge small">{{ styleLabel(t.teaching_style) }}</span></div>
        <div class="mstats">⭐ {{ t.avg_rating }} · {{ t.sessions_conducted }} sessions · 🪙 {{ t.rental_coins }}</div>
      </div>
      <p class="mintro">{{ t.tutor_intro }}</p>
      <div class="mtags"><span v-for="e in t.expertise" :key="e" class="tag">{{ e }}</span></div>
      <button @click="doRent(t)" class="btn-primary btn-small">Rent for 🪙{{ t.rental_coins }}</button>
    </div>
  </div>
</template>

<style scoped>
.card { background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.06); }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: .9rem; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-block { width: 100%; }
.btn-small { background: none; border: 1px solid var(--primary); color: var(--primary); padding: 4px 14px; border-radius: 6px; cursor: pointer; font-size: .8rem; }

.style-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; background: #ede9fe; color: #7c3aed; font-size: .78rem; font-weight: 600; margin-right: 6px; }
.style-badge.small { font-size: .7rem; padding: 1px 8px; }

.market-card { padding: 16px; margin-bottom: 10px; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; }
.mh { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; flex-wrap: wrap; gap: 4px; }
.mstats { font-size: .78rem; color: #888; }
.mintro { font-size: .85rem; color: #555; margin: 6px 0; }
.mtags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 10px; }
.tag { padding: 3px 10px; border-radius: 12px; background: #f1f5f9; font-size: .78rem; color: #475569; }

.empty { text-align: center; padding: 60px 20px; color: #888; }
</style>
