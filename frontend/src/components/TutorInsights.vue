<script setup lang="ts">
import { ref } from 'vue'
import api from '@/api'

const props = defineProps<{ lang: string; userId: string }>()

const loadInsights = ref(false)
const insightsResult = ref<any>(null)

async function doInsights() {
  loadInsights.value = true
  try {
    const res = await api.get('/tutor/insights', { params: { user_id: props.userId, lang: props.lang } })
    insightsResult.value = res.data
  } catch { /* ignore */ } finally { loadInsights.value = false }
}
</script>

<template>
  <div class="card">
    <button @click="doInsights" :disabled="loadInsights" class="btn-primary btn-block">
      {{ loadInsights ? '🔍 ...' : '🔍 Analyze My Progress' }}
    </button>

    <div v-if="insightsResult" class="insights-card">
      <p class="overall">{{ insightsResult.overall_assessment }}</p>
      <div class="score-circle">
        <svg viewBox="0 0 120 120" width="120" height="120">
          <circle cx="60" cy="60" r="52" fill="none" stroke="#eee" stroke-width="8"/>
          <circle cx="60" cy="60" r="52" fill="none" :stroke="insightsResult.learning_efficiency_score > 60 ? '#10b981' : '#f59e0b'"
            stroke-width="8" stroke-linecap="round"
            :stroke-dasharray="326" :stroke-dashoffset="326 - (326 * (insightsResult.learning_efficiency_score || 50) / 100)"
            transform="rotate(-90 60 60)"/>
          <text x="60" y="55" text-anchor="middle" font-size="18" font-weight="700" fill="#333">{{ insightsResult.learning_efficiency_score }}</text>
          <text x="60" y="72" text-anchor="middle" font-size="10" fill="#888">efficiency</text>
        </svg>
        <div class="rate-label">{{ insightsResult.improvement_rate?.replace(/_/g, ' ') }}</div>
      </div>

      <div class="ins-meta">
        <div><strong>💪 Strengths:</strong><ul><li v-for="s in insightsResult.strengths_developed" :key="s">{{ s }}</li></ul></div>
        <div><strong>🎯 To Improve:</strong><ul><li v-for="w in insightsResult.persistent_weaknesses" :key="w">{{ w }}</li></ul></div>
      </div>

      <div class="tips-box">
        <h4>📌 Personalized Tips</h4>
        <ul><li v-for="t in insightsResult.personalized_tips" :key="t">{{ t }}</li></ul>
      </div>

      <div class="milestone-box">
        <p>🎯 <strong>Next Milestone:</strong> {{ insightsResult.next_milestone }}</p>
      </div>

      <blockquote class="motivation">{{ insightsResult.motivation_boost }}</blockquote>
    </div>
  </div>
</template>

<style scoped>
.card { background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.06); }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: .9rem; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-block { width: 100%; }

.insights-card { margin-top: 20px; }
.overall { line-height: 1.6; margin-bottom: 16px; }
.score-circle { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.rate-label { text-transform: capitalize; font-size: .85rem; color: #666; }

.ins-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
.ins-meta ul { margin: 4px 0 0; padding-left: 18px; font-size: .85rem; }

.tips-box { padding: 12px; background: #f0f9ff; border-radius: 8px; margin-bottom: 12px; }
.tips-box h4 { margin: 0 0 6px; }
.tips-box ul { margin: 0; padding-left: 18px; font-size: .85rem; }

.milestone-box { padding: 10px 14px; background: #f0fdf4; border-radius: 8px; margin-bottom: 12px; }
.motivation { padding: 12px 18px; background: #faf5ff; border-left: 4px solid #7c3aed; border-radius: 0 8px 8px 0; font-style: italic; color: #4c1d95; margin: 0; }
</style>
