<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import api from '@/api'

const props = defineProps<{ lang: string; userId: string }>()

const chatMessages = ref<Array<{ role: string; content: string; ts: number }>>([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatPersona = ref<any>(null)

onMounted(() => loadChatHistory())

async function loadChatHistory() {
  try {
    const res = await api.get('/tutor/history', { params: { user_id: props.userId, lang: props.lang, limit: 30 } })
    chatMessages.value = (res.data.messages || []).map((m: any) => ({ role: m.role, content: m.content, ts: Date.now() }))
  } catch { /* empty */ }
}

async function initChatPersona() {
  try {
    const res = await api.post('/tutor/onboard', { user_id: props.userId, lang: props.lang })
    chatPersona.value = res.data.persona
    if (res.data.greeting) chatMessages.value.push({ role: 'tutor', content: res.data.greeting, ts: Date.now() })
  } catch { /* ignore */ }
}

async function sendChat() {
  const msg = chatInput.value.trim()
  if (!msg) return
  chatMessages.value.push({ role: 'user', content: msg, ts: Date.now() })
  chatInput.value = ''
  chatLoading.value = true
  try {
    const res = await api.post('/tutor/chat', { user_id: props.userId, message: msg, lang: props.lang })
    chatMessages.value.push({ role: 'tutor', content: res.data.reply, ts: Date.now() })
  } catch (e) { chatMessages.value.push({ role: 'tutor', content: 'Sorry, something went wrong.', ts: Date.now() }) }
  finally { chatLoading.value = false; nextTick(() => scrollChatBottom()) }
}

function scrollChatBottom() {
  const el = document.getElementById('tutor-chat-msgs')
  if (el) el.scrollTop = el.scrollHeight
}

function onChatKey(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat() }
}
</script>

<template>
  <div class="card chat-card">
    <div v-if="!chatPersona" class="chat-onboard">
      <p>👋 Loading your AI tutor...</p>
      <button @click="initChatPersona" class="btn-primary">Connect</button>
    </div>
    <div v-else class="chat-area">
      <div class="chat-header-inline">
        <span class="chat-avatar">{{ chatPersona.avatar_emoji || '🧑‍🏫' }}</span>
        <strong>{{ chatPersona.tutor_name }}</strong>
        <span class="chat-style">{{ chatPersona.teaching_style }}</span>
      </div>
      <div id="tutor-chat-msgs" class="chat-messages">
        <div v-if="chatMessages.length === 0" class="chat-empty">
          {{ chatPersona.tutor_intro || 'Say hi to your tutor! 👋' }}
        </div>
        <div v-for="(m, i) in chatMessages" :key="i" class="chat-msg-row" :class="m.role">
          <span class="chat-msg-bubble">{{ m.content }}</span>
        </div>
        <div v-if="chatLoading" class="chat-msg-row tutor">
          <span class="chat-msg-bubble typing">...</span>
        </div>
      </div>
      <div class="chat-input-row">
        <textarea v-model="chatInput" @keydown="onChatKey" placeholder="Ask your tutor..." rows="1" :disabled="chatLoading" />
        <button @click="sendChat" :disabled="chatLoading || !chatInput.trim()" class="btn-primary">➤</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card { background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.06); }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: .9rem; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }

.chat-card { display: flex; flex-direction: column; height: 60vh; min-height: 420px; }
.chat-onboard { text-align: center; padding: 60px 20px; }
.chat-onboard p { margin-bottom: 16px; color: #666; }
.chat-area { display: flex; flex-direction: column; flex: 1; overflow: hidden; }
.chat-header-inline { display: flex; align-items: center; gap: 10px; padding-bottom: 12px; border-bottom: 1px solid #eee; margin-bottom: 8px; }
.chat-avatar { font-size: 1.5rem; }
.chat-style { font-size: .75rem; color: #888; background: #f0f0f0; padding: 2px 8px; border-radius: 10px; }
.chat-messages { flex: 1; overflow-y: auto; padding: 8px 0; }
.chat-messages::-webkit-scrollbar { width: 4px; }
.chat-messages::-webkit-scrollbar-thumb { background: #ddd; border-radius: 2px; }
.chat-empty { text-align: center; color: #999; padding: 40px 20px; font-size: .9rem; line-height: 1.5; }
.chat-msg-row { display: flex; margin-bottom: 10px; }
.chat-msg-row.user { justify-content: flex-end; }
.chat-msg-row.tutor { justify-content: flex-start; }
.chat-msg-bubble { max-width: 78%; padding: 10px 14px; border-radius: 14px; font-size: .88rem; line-height: 1.5; word-break: break-word; }
.user .chat-msg-bubble { background: var(--primary); color: #fff; border-bottom-right-radius: 4px; }
.tutor .chat-msg-bubble { background: #f3f4f6; color: #333; border-bottom-left-radius: 4px; }
.chat-msg-bubble.typing { color: #999; font-style: italic; }
.chat-input-row { display: flex; gap: 8px; padding-top: 12px; border-top: 1px solid #eee; align-items: flex-end; }
.chat-input-row textarea { flex: 1; padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: .88rem; resize: none; font-family: inherit; outline: none; }
.chat-input-row textarea:focus { border-color: var(--primary); }
</style>
