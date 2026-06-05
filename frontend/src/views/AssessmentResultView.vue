<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import api from '@/api'
import { t } from '@/i18n'

// t imported from @/i18n

const route = useRoute()
const sessionId = route.params.id as string
const report = ref<any>(null)
const loading = ref(true)

onMounted(async () => {
  // 优先从 localStorage 读取（finishAssessment 已保存）
  const cached = localStorage.getItem('lawa_report_last')
  if (cached) {
    try {
      const data = JSON.parse(cached)
      // 适配 generate_report 返回格式 → 展示格式
      report.value = {
        level: data.overall_level || data.level || 'N/A',
        level_description: data.summary || '',
        score: data.total_score || data.score || 0,
        scores: data.dimension_scores || data.scores || {},
        recommendations: data.recommendations || [],
        strengths: data.strengths || [],
        weaknesses: data.weaknesses || [],
        questions_answered: data.questions_answered || 0,
      }
      loading.value = false
      return
    } catch { /* fall through to API */ }
  }
  // 兜底：尝试从后端获取（将来持久化后可用）
  try {
    const res = await api.get(`/assessment/${sessionId}`)
    report.value = res.data
  } catch { /* noop */ }
  finally { loading.value = false }
})

function cefrColor(level: string): string {
  const m: Record<string,string> = {A1:'#e74c3c',A2:'#e67e22',B1:'#f1c40f',B2:'#2ecc71',C1:'#3498db',C2:'#9b59b6'}
  return m[level] || '#888'
}
function barStyle(lvl: string) {
  const levels = ['A1','A2','B1','B2','C1','C2']
  const idx = levels.indexOf(lvl)
  if (idx === -1) return {}
  return { width: ((idx+1)/levels.length*100)+'%', background: cefrColor(lvl) }
}
</script>

<template>
  <div class="view-container">
    <div v-if="loading">{{ t('loading') }}</div>
    <div v-else-if="report">
      <h1>{{ t('assessment_result') }}</h1>
      <div class="card result-card">
        <div class="level-hero">
          <div class="level-badge" :style="{ background: cefrColor(report.level) }">{{ report.level }}</div>
          <div class="level-desc">
            <strong>{{ report.level_description || report.level }}</strong>
            <p>{{ t('score') }}：{{ report.score || 0 }}/100</p>
          </div>
        </div>
        <div class="skill-bar">
          <div class="bar-label">{{ t('overall') }}</div>
          <div class="bar-track"><div class="bar-fill" :style="barStyle(report.level)"></div></div>
        </div>
        <div v-if="report.scores" class="skill-details">
          <div v-for="(val,key) in report.scores" :key="key" class="skill-row">
            <span>{{ val.label || key }}</span>
            <span class="skill-val">{{ typeof val === 'object' ? (val.average_score || val.score || 0) : val }}/10</span>
          </div>
        </div>
        <div v-if="report.recommendations" class="recommendations">
          <h3>{{ t('recommendations') }}</h3>
          <ul><li v-for="r in report.recommendations" :key="r">{{ r }}</li></ul>
        </div>
      </div>
      <div class="actions">
        <router-link to="/plan" class="btn-primary">{{ t('view_plan') }}</router-link>
        <router-link to="/companion" class="btn-secondary">{{ t('ai_companion') }}</router-link>
        <router-link to="/assessment" class="btn-outline">{{ t('retake') }}</router-link>
      </div>
    </div>
    <div v-else class="empty"><p>{{ t('result_not_found') }}</p></div>
  </div>
</template>

<style scoped>
.view-container { max-width: 720px; margin: 0 auto; padding: 24px; }
.card { background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.result-card { margin: 20px 0; }
.level-hero { display: flex; gap: 16px; align-items: center; margin-bottom: 24px; }
.level-badge { width: 80px; height: 80px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 1.8rem; font-weight: 700; }
.level-desc { flex: 1; } .level-desc p { margin: 4px 0; color: #666; }
.skill-bar { margin-bottom: 20px; }
.bar-label { font-size: .85rem; margin-bottom: 4px; }
.bar-track { height: 12px; background: #e9ecef; border-radius: 20px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 20px; transition: width .5s; }
.skill-details { margin-bottom: 20px; }
.skill-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: .9rem; }
.recommendations ul { padding-left: 20px; } .recommendations li { margin: 6px 0; color: #666; }
.actions { display: flex; gap: 12px; }
.btn-primary,.btn-secondary,.btn-outline { padding: 12px 24px; border-radius: 8px; font-size: .95rem; cursor: pointer; text-decoration: none; display: inline-block; }
.btn-primary { background: var(--primary); color: #fff; border: none; }
.btn-secondary { background: #2ecc71; color: #fff; border: none; }
.btn-outline { background: none; border: 1px solid var(--primary); color: var(--primary); }
.empty { text-align: center; padding: 60px; color: #888; }
</style>
