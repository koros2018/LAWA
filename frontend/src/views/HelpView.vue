<script setup lang="ts">
import { ref, onMounted } from 'vue'

import api from '@/api'
import { t } from '@/i18n'

// t imported from @/i18n

const requests = ref<any[]>([])
const loading = ref(true)
const user = ref<any>({})
const showCreate = ref(false)
const newTitle = ref(''); const newContent = ref('')
const newReward = ref(0); const newLang = ref('en')

onMounted(async () => {
  const u = localStorage.getItem('lawa_user')
  if (u) user.value = JSON.parse(u)
  try {
    const res = await api.get('/community/help?limit=30')
    requests.value = res.data.requests || []
  } catch { /* noop */ }
  finally { loading.value = false }
})

async function postHelp() {
  if (!newTitle.value.trim()) return
  try {
    await api.post('/community/help/post', {
      user_id: user.value.id||user.value.sub||'anonymous',
      title: newTitle.value, content: newContent.value,
      reward_coin: newReward.value, language: newLang.value,
    })
    newTitle.value=''; newContent.value=''; newReward.value=0; showCreate.value=false
    const res = await api.get('/community/help?limit=30')
    requests.value = res.data.requests || []
  } catch { /* noop */ }
}

function statusLabel(s: string) { return s==='open'?'待回答':'已解决' }
</script>

<template>
  <div class="view-container">
    <div class="hr"><h1>{{ t('help') }}</h1>
      <button @click="showCreate=!showCreate" class="btn-primary">{{ showCreate?'✕':'＋'+t('post_help') }}</button>
    </div>
    <div v-if="showCreate" class="card create-card">
      <input v-model="newTitle" :placeholder="t('help_title')" />
      <textarea v-model="newContent" :placeholder="t('help_description')" rows="3"></textarea>
      <div class="fr">
        <select v-model="newLang"><option value="en">English</option><option value="zh-CN">中文</option></select>
        <input v-model.number="newReward" type="number" :placeholder="t('reward_coin')" />
        <button @click="postHelp" class="btn-primary">📤</button>
      </div>
    </div>
    <div v-if="loading">{{ t('loading') }}</div>
    <div v-else-if="requests.length===0" class="empty">{{ t('no_help') }}</div>
    <div v-else class="help-list">
      <div v-for="r in requests" :key="r.id" class="card help-card">
        <div class="hh"><span :class="['badge',r.status]">{{ statusLabel(r.status) }}</span><span v-if="r.reward_coin" class="reward">🪙{{ r.reward_coin }}</span></div>
        <h4>{{ r.title }}</h4>
        <p v-if="r.content" class="desc">{{ r.content.slice(0,120) }}{{ r.content.length>120?'...':'' }}</p>
        <div class="hf"><span>{{ r.user_id?.slice(0,8)||'匿名' }}</span><span>{{ r.responses?.length||0 }} 条回答</span><span>{{ r.created_at?new Date(r.created_at).toLocaleDateString():'' }}</span></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 720px; margin:0 auto; padding:24px; }
.hr { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.hr h1 { margin:0; }
.btn-primary { background:var(--primary); color:white; border:none; padding:8px 16px; border-radius:8px; cursor:pointer; font-size:.9rem; }
.card { background:white; border-radius:12px; padding:16px; box-shadow:0 2px 8px rgba(0,0,0,.08); margin-bottom:8px; }
.create-card input, .create-card textarea, .create-card select { width:100%; padding:10px; border:1px solid #ddd; border-radius:8px; margin-bottom:8px; font-size:.9rem; box-sizing:border-box; }
.fr { display:flex; gap:8px; } .fr select,.fr input { flex:1; }
.hh { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.badge { padding:2px 10px; border-radius:12px; font-size:.75rem; font-weight:600; }
.badge.open { background:#dbeafe; color:#1e40af; } .badge.closed { background:#d1fae5; color:#065f46; }
.reward { font-weight:600; color:#f59e0b; font-size:.85rem; }
h4 { margin:0 0 6px; } .desc { color:#666; font-size:.85rem; margin:0 0 8px; }
.hf { display:flex; gap:16px; font-size:.8rem; color:#999; }
.empty { text-align:center; padding:60px; color:#888; }
</style>
