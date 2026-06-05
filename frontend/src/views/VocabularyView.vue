import { t } from '@/i18n'
<script setup lang="ts">
import { ref, onMounted } from 'vue'
// t imported from @/i18n

import api from '@/api'


const words = ref<any[]>([])
const loading = ref(true)
const tab = ref<'pending'|'mastered'>('pending')

onMounted(async () => {
  try {
    const res = await api.get('/companion/vocabulary')
    words.value = res.data.words || res.data
  } catch { /* noop */ }
  finally { loading.value = false }
})
</script>

<template>
  <div class="view-container">
    <h1>{{ t('vocabulary') }}</h1>
    <div class="tabs">
      <button :class="{active:tab==='pending'}" @click="tab='pending'">{{ t('to_review') }}</button>
      <button :class="{active:tab==='mastered'}" @click="tab='mastered'">{{ t('mastered') }}</button>
    </div>
    <div v-if="loading">{{ t('loading') }}</div>
    <div v-else-if="words.length===0" class="empty">
      <p>📚 {{ t('no_vocab_yet') }}</p>
      <router-link to="/companion" class="btn-primary">{{ t('companion') }}</router-link>
    </div>
    <div v-else class="vocab-list">
      <div v-for="w in words" :key="w.id||w.word" class="card vocab-card">
        <div class="vocab-main">
          <span class="word">{{ w.word }}</span>
          <span class="trans">{{ w.translation }}</span>
        </div>
        <p v-if="w.example" class="sentence">📖 {{ w.example }}</p>
        <div class="vocab-meta">
          <span class="cnt">{{ t('reviewed') }}：{{ w.review_count||0 }}x</span>
          <span class="bar-track"><span class="bar-fill" :style="{width:Math.min((w.review_count||0)*25,100)+'%'}"></span></span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 720px; margin: 0 auto; padding: 24px; }
.card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tabs button { padding: 8px 20px; border: 1px solid #ddd; border-radius: 8px; background: #fff; cursor: pointer; }
.tabs button.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.vocab-list { display: flex; flex-direction: column; gap: 8px; }
.vocab-main { display: flex; gap: 12px; align-items: baseline; }
.word { font-size: 1.1rem; font-weight: 600; }
.trans { font-size: .9rem; color: #888; }
.sentence { margin: 8px 0 0; font-size: .85rem; color: #666; font-style: italic; }
.vocab-meta { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
.cnt { font-size: .75rem; color: #aaa; }
.bar-track { flex:1; height:6px; background:#e9ecef; border-radius:10px; overflow:hidden; }
.bar-fill { height:100%; background:#2ecc71; border-radius:10px; }
.empty { text-align: center; padding: 60px; color: #888; }
.empty p { font-size: 1.2rem; margin-bottom: 20px; }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 12px 24px; border-radius: 8px; text-decoration: none; display: inline-block; }
</style>
