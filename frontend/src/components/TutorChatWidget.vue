<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import api, { SLOWER } from '@/api'

// ── State ──
const open = ref(false)
const messages = ref<Array<{ role: string; content: string; ts: number }>>([])
const input = ref('')
const loading = ref(false)
const persona = ref<any>(null)
const onboarded = ref(false)
const adjusting = ref(false)
const unread = ref(0)

// ── Computed ──
const userId = () => {
  try { const u = JSON.parse(localStorage.getItem('lawa_user') || 'null'); return u?.id || u?.sub || 'anonymous' }
  catch { return 'anonymous' }
}

const learnerName = () => {
  try { const u = JSON.parse(localStorage.getItem('lawa_user') || 'null'); return u?.username || 'Learner' }
  catch { return 'Learner' }
}

// ── On mounted: auto onboard + load history ──
onMounted(async () => {
  await ensureOnboarded()
  await loadHistory()
})

async function ensureOnboarded() {
  try {
    const res = await api.post('/tutor/onboard', { user_id: userId(), lang: 'en', learner_name: learnerName() }, { timeout: SLOWER })
    persona.value = res.data.persona
    onboarded.value = true
  } catch { /* will try again on first chat */ }
}

async function loadHistory() {
  try {
    const res = await api.get('/tutor/history', { params: { user_id: userId(), limit: 30 } })
    messages.value = (res.data.messages || []).map((m: any) => ({ role: m.role, content: m.content, ts: Date.now() }))
  } catch { /* silent */ }
}

// ── Chat ──
async function send() {
  const msg = input.value.trim()
  if (!msg || loading.value) return

  messages.value.push({ role: 'user', content: msg, ts: Date.now() })
  input.value = ''
  loading.value = true

  try {
    const res = await api.post('/tutor/chat', {
      user_id: userId(),
      message: msg,
      learner_name: learnerName(),
    }, { timeout: SLOWER })
    messages.value.push({ role: 'tutor', content: res.data.reply, ts: Date.now() })
    if (!persona.value) {
      persona.value = { tutor_name: res.data.tutor_name, avatar_emoji: res.data.avatar }
    }
    await nextTick()
    scrollBottom()
  } catch (e: any) {
    messages.value.push({ role: 'tutor', content: 'Hmm, my voice is a bit hoarse... Can you try again? 🦜', ts: Date.now() })
  } finally {
    loading.value = false
  }
}

async function adjustDifficulty(direction: string) {
  adjusting.value = true
  try {
    const res = await api.post('/tutor/adjust', { user_id: userId(), direction }, { timeout: SLOWER })
    messages.value.push({ role: 'tutor', content: res.data.message, ts: Date.now() })
    await nextTick(); scrollBottom()
  } catch { /* */ }
  finally { adjusting.value = false }
}

function scrollBottom() {
  const el = document.getElementById('tutor-chat-messages')
  if (el) el.scrollTop = el.scrollHeight
}

function toggle() {
  open.value = !open.value
  if (open.value) { unread.value = 0; nextTick(() => scrollBottom()) }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
}

// Watch for new messages when closed
watch(() => messages.value.length, (n, o) => {
  if (!open.value && n > o) unread.value += (n - o)
})
</script>

<template>
  <!-- Floating Button -->
  <div class="tutor-float" :class="{ open }">
    <button class="tutor-fab" @click="toggle" :title="persona?.tutor_name || 'AI Tutor'">
      <span class="fab-icon">{{ persona?.avatar_emoji || '🧑‍🏫' }}</span>
      <span v-if="unread > 0" class="badge">{{ unread > 9 ? '9+' : unread }}</span>
    </button>

    <!-- Chat Panel -->
    <Transition name="slide">
      <div v-if="open" class="tutor-panel">
        <!-- Header -->
        <div class="panel-header">
          <div class="tutor-info">
            <span class="tutor-avatar">{{ persona?.avatar_emoji || '🧑‍🏫' }}</span>
            <div>
              <div class="tutor-name">{{ persona?.tutor_name || 'AI Tutor' }}</div>
              <div class="tutor-status">🟢 Online · {{ persona?.teaching_style || 'mentor' }}</div>
            </div>
          </div>
          <div class="header-actions">
            <button class="icon-btn" title="Easier" @click="adjustDifficulty('easier')" :disabled="adjusting">🔽</button>
            <button class="icon-btn" title="Harder" @click="adjustDifficulty('harder')" :disabled="adjusting">🔼</button>
            <button class="icon-btn close-btn" @click="toggle">✕</button>
          </div>
        </div>

        <!-- Messages -->
        <div id="tutor-chat-messages" class="panel-messages">
          <div v-if="!onboarded" class="msg-row onboarding">
            <span class="msg-bubble tutor">👋 Hey! I'm your AI language tutor. Ask me anything about language learning, or just say hi!</span>
          </div>
          <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
            <span class="msg-bubble">{{ m.content }}</span>
          </div>
          <div v-if="loading" class="msg-row tutor">
            <span class="msg-bubble typing"><span class="dot">●</span><span class="dot">●</span><span class="dot">●</span></span>
          </div>
        </div>

        <!-- Input -->
        <div class="panel-input">
          <textarea
            v-model="input"
            @keydown="onKeydown"
            placeholder="Ask your tutor anything..."
            rows="1"
            :disabled="loading"
          />
          <button class="send-btn" @click="send" :disabled="loading || !input.trim()">➤</button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* ── Floating FAB ── */
.tutor-float { position: fixed; bottom: 24px; right: 24px; z-index: 9999; }
.tutor-fab {
  width: 56px; height: 56px; border-radius: 50%; border: none;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white; cursor: pointer; box-shadow: 0 4px 16px rgba(102,126,234,.4);
  display: flex; align-items: center; justify-content: center; position: relative;
  transition: transform .2s, box-shadow .2s;
}
.tutor-fab:hover { transform: scale(1.08); box-shadow: 0 6px 20px rgba(102,126,234,.5); }
.tutor-float.open .tutor-fab { transform: scale(0); pointer-events: none; }
.fab-icon { font-size: 1.5rem; }

.badge {
  position: absolute; top: -4px; right: -4px;
  background: #ef4444; color: white; font-size: 0.7rem; font-weight: 700;
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  border: 2px solid white;
}

/* ── Chat Panel ── */
.tutor-panel {
  position: fixed; bottom: 24px; right: 24px;
  width: 380px; max-width: calc(100vw - 48px);
  height: 560px; max-height: calc(100vh - 120px);
  background: white; border-radius: 16px; box-shadow: 0 8px 32px rgba(0,0,0,.15);
  display: flex; flex-direction: column; overflow: hidden;
}

/* Panel Header */
.panel-header {
  padding: 14px 16px; border-bottom: 1px solid #f0f0f0;
  display: flex; align-items: center; justify-content: space-between;
  background: linear-gradient(135deg, #667eea, #764ba2); color: white;
}
.tutor-info { display: flex; align-items: center; gap: 10px; }
.tutor-avatar { font-size: 1.6rem; }
.tutor-name { font-weight: 700; font-size: .95rem; }
.tutor-status { font-size: .7rem; opacity: .85; }
.header-actions { display: flex; gap: 4px; }
.icon-btn {
  width: 30px; height: 30px; border-radius: 50%; border: none;
  background: rgba(255,255,255,.2); color: white; cursor: pointer;
  font-size: .8rem; display: flex; align-items: center; justify-content: center;
  transition: background .15s;
}
.icon-btn:hover { background: rgba(255,255,255,.35); }
.icon-btn:disabled { opacity: .4; cursor: not-allowed; }
.close-btn { font-size: 1rem; font-weight: 700; }

/* Messages */
.panel-messages { flex: 1; overflow-y: auto; padding: 16px; }
.panel-messages::-webkit-scrollbar { width: 4px; }
.panel-messages::-webkit-scrollbar-thumb { background: #ddd; border-radius: 2px; }

.msg-row { margin-bottom: 12px; display: flex; }
.msg-row.user { justify-content: flex-end; }
.msg-row.tutor { justify-content: flex-start; }
.msg-row.onboarding { justify-content: center; }

.msg-bubble {
  max-width: 82%; padding: 10px 14px; border-radius: 16px;
  font-size: .88rem; line-height: 1.5; word-break: break-word;
}
.user .msg-bubble { background: #667eea; color: white; border-bottom-right-radius: 4px; }
.tutor .msg-bubble { background: #f3f4f6; color: #333; border-bottom-left-radius: 4px; }
.onboarding .msg-bubble { background: #fef3c7; color: #92400e; border-radius: 12px; text-align: center; }

/* Typing indicator */
.typing { padding: 14px 18px; }
.dot { animation: blink 1.4s infinite both; font-size: .5rem; margin: 0 2px; }
.dot:nth-child(2) { animation-delay: .2s; }
.dot:nth-child(3) { animation-delay: .4s; }
@keyframes blink { 0%,80%,100% { opacity: 0; } 40% { opacity: 1; } }

/* Input */
.panel-input {
  padding: 12px 16px; border-top: 1px solid #f0f0f0;
  display: flex; gap: 8px; align-items: flex-end;
}
.panel-input textarea {
  flex: 1; padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 20px;
  font-size: .88rem; resize: none; outline: none; font-family: inherit;
  max-height: 80px; transition: border-color .15s;
}
.panel-input textarea:focus { border-color: #667eea; }
.send-btn {
  width: 38px; height: 38px; border-radius: 50%; border: none;
  background: #667eea; color: white; cursor: pointer; font-size: 1rem;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s, transform .15s; flex-shrink: 0;
}
.send-btn:hover:not(:disabled) { background: #5a6fd6; transform: scale(1.05); }
.send-btn:disabled { background: #ccc; cursor: not-allowed; }

/* Transition */
.slide-enter-active { transition: all .25s cubic-bezier(.4,0,.2,1); }
.slide-leave-active { transition: all .2s cubic-bezier(.4,0,.2,1); }
.slide-enter-from, .slide-leave-to {
  opacity: 0; transform: translateY(20px) scale(.95);
}
</style>
