<script setup lang="ts">
import { ref, onMounted } from 'vue'

import api from '@/api'
import { t } from '@/i18n'

// t imported from @/i18n

const candidates = ref<any[]>([])
const loading = ref(true)
const showRegister = ref(false)
const user = ref<any>({})
const nativeLang = ref('zh-CN'); const targetLang = ref('en')
const level = ref('A2'); const interests = ref(''); const bio = ref('')
const levelLabels: Record<string,string> = { A1:'入门',A2:'初级',B1:'中级',B2:'中高级',C1:'高级',C2:'精通' }

onMounted(async () => {
  const u = localStorage.getItem('lawa_user')
  if (u) user.value = JSON.parse(u)
  try {
    const res = await api.post('/community/match/find', {
      user_id: user.value.id||user.value.sub||'anonymous', limit: 20,
    })
    candidates.value = res.data.candidates || []
  } catch { showRegister.value = true }
  finally { loading.value = false }
})

async function doRegister() {
  try {
    await api.post('/community/match/register', {
      user_id: user.value.id||user.value.sub||'anonymous',
      native_language: nativeLang.value, target_language: targetLang.value,
      level: level.value,
      interests: interests.value?interests.value.split(',').map((s:string)=>s.trim()):[],
      bio: bio.value,
    })
    showRegister.value = false
    const res = await api.post('/community/match/find', {
      user_id: user.value.id||user.value.sub||'anonymous', limit: 20,
    })
    candidates.value = res.data.candidates || []
  } catch { /* noop */ }
}

async function matchUser(uid: string) {
  try {
    await api.post('/community/match/pair', {
      user_a: user.value.id||user.value.sub||'anonymous', user_b: uid,
    })
    alert(t('match_sent'))
  } catch { /* noop */ }
}
</script>

<template>
  <div class="view-container">
    <h1>{{ t('match') }}</h1>
    <div v-if="showRegister" class="card">
      <h3>📋 {{ t('match_profile') }}</h3>
      <div class="form-row">
        <div class="fg">
          <label>{{ t('native_language') }}</label>
          <select v-model="nativeLang"><option value="zh-CN">中文</option><option value="en">English</option><option value="ja">日本語</option></select>
        </div>
        <div class="fg">
          <label>{{ t('target_language') }}</label>
          <select v-model="targetLang"><option value="en">English</option><option value="zh-CN">中文</option><option value="ja">日本語</option></select>
        </div>
      </div>
      <div class="fg"><label>{{ t('level') }}</label>
        <select v-model="level"><option v-for="l in ['A1','A2','B1','B2','C1','C2']" :key="l" :value="l">{{ levelLabels[l] }} ({{ l }})</option></select>
      </div>
      <div class="fg"><label>{{ t('interests') }}</label><input v-model="interests" :placeholder="t('interests_hint')" /></div>
      <div class="fg"><label>{{ t('bio') }}</label><textarea v-model="bio" rows="2"></textarea></div>
      <button @click="doRegister" class="btn-primary btn-block">🤝 {{ t('register_match') }}</button>
    </div>
    <div v-else-if="loading">{{ t('loading') }}</div>
    <div v-else>
      <div v-for="c in candidates" :key="c.user_id" class="card candidate-card">
        <div class="ch">
          <span class="ms">{{ c.match_score }}%</span>
          <button @click="matchUser(c.user_id)" class="btn-small">🤝 {{ t('match_now') }}</button>
        </div>
        <div class="lp">🌐 {{ c.native_language }} → {{ c.target_language }}</div>
        <div class="meta">📊 {{ levelLabels[c.level]||c.level }} · {{ c.interests?.join(', ')||'无' }}</div>
        <p v-if="c.bio" class="bio">{{ c.bio }}</p>
      </div>
      <div v-if="candidates.length===0" class="empty">{{ t('no_matches') }}</div>
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 720px; margin:0 auto; padding:24px; }
.card { background:white; border-radius:12px; padding:24px; box-shadow:0 2px 8px rgba(0,0,0,.08); margin-bottom:12px; }
.fg { margin-bottom:14px; }
label { display:block; margin-bottom:4px; font-weight:500; font-size:.85rem; }
input,select,textarea { width:100%; padding:10px; border:1px solid #ddd; border-radius:8px; font-size:.95rem; box-sizing:border-box; }
.form-row { display:flex; gap:12px; } .form-row .fg { flex:1; }
.btn-primary { background:var(--primary); color:white; border:none; padding:12px; border-radius:8px; cursor:pointer; font-size:.95rem; }
.btn-block { width:100%; }
.btn-small { background:none; border:1px solid var(--primary); color:var(--primary); padding:4px 12px; border-radius:6px; cursor:pointer; font-size:.8rem; }
.ch { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.ms { font-weight:700; color:#059669; }
.lp { font-size:.9rem; margin-bottom:4px; }
.meta { font-size:.8rem; color:#666; margin-bottom:4px; }
.bio { font-size:.85rem; color:#444; margin:8px 0 0; }
.empty { text-align:center; padding:60px; color:#888; }
</style>
