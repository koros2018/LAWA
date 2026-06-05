<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import api from '@/api'

const props = defineProps<{ lang: string; userId: string }>()
const emit = defineEmits<{ evolve: [result: any] }>()

const loading = ref(false)
const profile = ref<any>(null)
const evolLogs = ref<any[]>([])
const loadEvolve = ref(false)
const evolveResult = ref<any>(null)

const styleLabel = (s: string): string => {
  const m: Record<string,string> = { patient_explainer:'耐心讲解', drill_master:'训练大师', conversationalist:'对话达人', storyteller:'故事大王', grammar_nerd:'语法专精', coach:'教练型' }
  return m[s] || s
}

onMounted(() => loadProfile())
watch(() => props.lang, () => loadProfile())

async function loadProfile() {
  loading.value = true
  try {
    const res = await api.get('/tutor/profile', { params: { user_id: props.userId, lang: props.lang } })
    profile.value = res.data.profile || { tutor_name: 'Alex', lang: props.lang, teaching_style: 'patient_explainer', personality: ['encouraging'], expertise: ['grammar'], default_strategies: [], avg_rating: 0, sessions_conducted: 0, rental_coins: 0, tutor_intro: '' }
    evolLogs.value = res.data.evolution_history || []
  } catch { profile.value = null } finally { loading.value = false }
}

async function doEvolve() {
  loadEvolve.value = true
  try {
    const res = await api.post('/tutor/evolve', { user_id: props.userId, lang: props.lang, persona: profile.value, history: evolLogs.value })
    evolveResult.value = res.data
    emit('evolve', res.data)
  } catch (e) { /* ignore */ } finally { loadEvolve.value = false }
}
</script>

<template>
  <div v-if="loading">Loading...</div>
  <div v-else-if="!profile" class="empty">No data</div>
  <div v-else class="profile-card card">
    <div class="pr">
      <div class="avatar">🧑‍🏫</div>
      <div class="info">
        <h2>{{ profile.tutor_name }}</h2>
        <span class="style-badge">{{ styleLabel(profile.teaching_style) }}</span>
        <span class="lang-badge">{{ profile.lang === 'en' ? 'English' : '中文' }}</span>
      </div>
    </div>
    <p class="intro">{{ profile.tutor_intro }}</p>

    <div class="meta-row">
      <div class="meta-item"><span class="label">Sessions</span><span class="value">{{ profile.sessions_conducted }}</span></div>
      <div class="meta-item"><span class="label">Rating</span><span class="value">⭐ {{ profile.avg_rating?.toFixed(1) || 'N/A' }}</span></div>
      <div class="meta-item"><span class="label">Rental</span><span class="value">🪙 {{ profile.rental_coins || 0 }}</span></div>
    </div>

    <div class="tag-groups">
      <div class="tg"><h4>🎯 Expertise</h4><div class="tags"><span v-for="e in profile.expertise" :key="e" class="tag">{{ e }}</span></div></div>
      <div class="tg"><h4>💡 Strategies</h4><div class="tags"><span v-for="s in profile.default_strategies" :key="s" class="tag strategy">{{ s }}</span></div></div>
      <div class="tg"><h4>😊 Personality</h4><div class="tags"><span v-for="p in profile.personality" :key="p" class="tag personality">{{ p }}</span></div></div>
    </div>

    <div class="evolve-section">
      <button @click="doEvolve" :disabled="loadEvolve" class="btn-primary btn-block">
        {{ loadEvolve ? '🔄 Evolving...' : '🧬 Evolve Tutor' }}
      </button>
      <div v-if="evolveResult" class="evolve-result">
        <p><strong>New Style:</strong> {{ styleLabel(evolveResult.evolved_profile?.teaching_style) }}</p>
        <p><strong>Focus Next Week:</strong> {{ evolveResult.focus_areas_next_week?.join(', ') || 'N/A' }}</p>
        <p><strong>Est. Weeks to Target:</strong> {{ evolveResult.estimated_weeks_to_target }}</p>
      </div>
    </div>

    <div v-if="evolLogs.length" class="history">
      <h4>📜 Evolution History</h4>
      <div v-for="(log,i) in evolLogs" :key="i" class="log-item">
        <span class="log-ts">{{ log.timestamp?.slice(0,10) || 'now' }}</span>
        <span>{{ log.before_style }} → {{ log.after_style }}</span>
        <span class="log-note">{{ log.note?.slice(0,60) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card { background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.06); }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: .9rem; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-block { width: 100%; }

.profile-card .pr { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.avatar { font-size: 3rem; }
.info h2 { margin: 0 0 4px; }
.style-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; background: #ede9fe; color: #7c3aed; font-size: .78rem; font-weight: 600; margin-right: 6px; }
.lang-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; background: #e0f2fe; color: #0369a1; font-size: .78rem; }
.intro { color: #555; margin: 8px 0 16px; line-height: 1.5; }

.meta-row { display: flex; gap: 20px; margin-bottom: 16px; }
.meta-item { display: flex; flex-direction: column; background: #f8fafc; padding: 12px 20px; border-radius: 10px; }
.meta-item .label { font-size: .75rem; color: #888; }
.meta-item .value { font-size: 1.1rem; font-weight: 700; }

.tag-groups { margin-bottom: 16px; }
.tg { margin-bottom: 10px; }
.tg h4 { margin: 0 0 6px; font-size: .85rem; }
.tags { display: flex; gap: 6px; flex-wrap: wrap; }
.tag { padding: 3px 10px; border-radius: 12px; background: #f1f5f9; font-size: .78rem; color: #475569; }
.tag.strategy { background: #fef3c7; color: #92400e; }
.tag.personality { background: #d1fae5; color: #065f46; }

.evolve-section { margin-top: 16px; padding-top: 16px; border-top: 1px solid #eee; }
.evolve-result { margin-top: 12px; padding: 12px; background: #f0fdf4; border-radius: 8px; font-size: .85rem; }
.evolve-result p { margin: 4px 0; }

.history { margin-top: 16px; }
.history h4 { margin: 0 0 8px; font-size: .85rem; }
.log-item { display: flex; gap: 12px; padding: 6px 0; font-size: .8rem; border-bottom: 1px solid #f0f0f0; }
.log-ts { color: #999; min-width: 80px; }
.log-note { color: #666; }
.empty { text-align: center; padding: 60px 20px; color: #888; }
</style>
