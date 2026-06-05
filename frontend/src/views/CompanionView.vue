<script setup lang="ts">
import { ref, onMounted } from 'vue'

import api, { SLOWER } from '@/api'
import { t } from '@/i18n'

// t imported from @/i18n

const scenarios = ref<any[]>([])
const session = ref<any>(null)
const messages = ref<any[]>([])
const activeScenario = ref<any>(null)
const inputText = ref('')
const loading = ref(true)
const chatting = ref(false)
const corrections = ref<any[]>([])

onMounted(async () => {
  try {
    const res = await api.get('/companion/scenarios')
    scenarios.value = res.data.scenarios || res.data
  } catch { /* noop */ }
  finally { loading.value = false }
})

async function startScenario(scenario: any) {
  activeScenario.value = scenario
  chatting.value = true
  corrections.value = []
  try {
    const res = await api.post('/companion/start', {
      scenario_id: scenario.id,
      language: scenario.language || 'en',
    }, { timeout: SLOWER })
    session.value = res.data.session || res.data
    messages.value = res.data.messages || []
  } catch { /* noop */ }
}

async function sendMessage() {
  if (!inputText.value.trim() || !session.value) return
  const text = inputText.value
  messages.value.push({ role: 'user', content: text, timestamp: Date.now() })
  inputText.value = ''
  try {
    const sid = session.value.id || session.value.session_id
    const res = await api.post(`/companion/send/${sid}`, { message: text }, { timeout: SLOWER })
    messages.value.push({ role: 'assistant', content: res.data.message, timestamp: Date.now() })
    if (res.data.corrections?.length) corrections.value = res.data.corrections
  } catch { /* noop */ }
}

async function endSession() {
  try {
    const sid = session.value.id || session.value.session_id
    await api.post(`/companion/end/${sid}`)
  } catch { /* noop */ }
  chatting.value = false; activeScenario.value = null; session.value = null
}
</script>

<template>
  <div class="view-container">
    <div v-if="!chatting">
      <h1>{{ t('companion') }}</h1>
      <div v-if="loading">{{ t('loading') }}</div>
      <div v-else class="scenario-grid">
        <div v-for="s in scenarios" :key="s.id" class="scenario-card" @click="startScenario(s)">
          <div class="scenario-icon">{{ s.icon || '💬' }}</div>
          <div class="scenario-info">
            <h4>{{ s.title }}</h4>
            <p>{{ s.description }}</p>
            <span class="lang-badge">{{ s.language === 'zh-CN' ? '中文' : 'EN' }}</span>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="chat-interface">
      <div class="chat-header">
        <h3>{{ activeScenario?.title }}</h3>
        <button @click="endSession" class="btn-small">{{ t('end') }}</button>
      </div>
      <div class="chat-messages" ref="chatRef">
        <div v-for="(msg, i) in messages" :key="i" :class="['msg', msg.role]">
          <div class="bubble">{{ msg.content }}</div>
          <div class="msg-time">{{ msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : '' }}</div>
        </div>
      </div>
      <div v-if="corrections.length" class="corrections-box">
        <h4>✏️ {{ t('corrections') }}</h4>
        <div v-for="(c, i) in corrections" :key="i" class="corr-item">
          <div class="corr-old">❌ {{ c.original }}</div>
          <div class="corr-new">✅ {{ c.corrected }}</div>
          <p v-if="c.explanation" class="corr-explain">{{ c.explanation }}</p>
        </div>
      </div>
      <div class="chat-input">
        <input v-model="inputText" @keyup.enter="sendMessage" :placeholder="t('type_message')" />
        <button @click="sendMessage" class="btn-primary">➤</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 800px; margin: 0 auto; padding: 24px; }
.scenario-grid { display: flex; flex-direction: column; gap: 8px; }
.scenario-card { display: flex; gap: 16px; background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,.08); cursor: pointer; transition: transform .15s; }
.scenario-card:hover { transform: translateY(-2px); }
.scenario-icon { font-size: 2.5rem; }
.scenario-info h4 { margin: 0 0 4px; }
.scenario-info p { margin: 0 0 8px; color: #666; font-size: .85rem; }
.lang-badge { background: #eef2ff; color: var(--primary); padding: 2px 8px; border-radius: 4px; font-size: .75rem; }
.chat-interface { display: flex; flex-direction: column; height: calc(100vh - 160px); }
.chat-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.btn-small { background: none; border: 1px solid #e53e3e; color: #e53e3e; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: .85rem; }
.chat-messages { flex: 1; overflow-y: auto; padding: 12px; background: #f8f9fa; border-radius: 12px; display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.msg { max-width: 80%; }
.msg.user { align-self: flex-end; }
.msg.assistant { align-self: flex-start; }
.bubble { padding: 10px 14px; border-radius: 16px; font-size: .95rem; }
.msg.user .bubble { background: var(--primary); color: #fff; border-bottom-right-radius: 4px; }
.msg.assistant .bubble { background: #fff; border: 1px solid #e9ecef; border-bottom-left-radius: 4px; }
.msg-time { font-size: .7rem; color: #aaa; margin-top: 2px; text-align: right; }
.corrections-box { background: #fffbe6; border: 1px solid #fde68a; border-radius: 12px; padding: 12px; margin-bottom: 12px; max-height: 200px; overflow-y: auto; }
.corrections-box h4 { margin: 0 0 8px; }
.corr-item { margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #fde68a; }
.corr-old { color: #dc2626; font-size: .85rem; }
.corr-new { color: #16a34a; font-size: .85rem; }
.corr-explain { margin: 4px 0 0; font-size: .8rem; color: #666; }
.chat-input { display: flex; gap: 8px; }
.chat-input input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 24px; font-size: 1rem; }
.chat-input input:focus { outline: none; border-color: var(--primary); }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 10px 20px; border-radius: 24px; cursor: pointer; }
</style>
