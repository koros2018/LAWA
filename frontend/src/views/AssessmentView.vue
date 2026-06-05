<script setup lang="ts">
import { ref, computed, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api, { SLOWER } from '@/api'
import { t } from '@/i18n'

const router = useRouter()
const language = ref<'en' | 'zh'>('en')
const loading = ref(false)
const error = ref('')
const assessmentId = ref('')
const started = ref(false)

const dimensions = ref<string[]>([])
const levelEstimate = ref('B1')
const currentQuestion = ref<any>(null)
const userAnswer = ref('')
const selectedOption = ref('')
const previousResults = ref<any[]>([])
const totalQuestions = ref(0)
const lastFeedback = ref('')
const feedbackKey = ref(0)

// ⏱️ 自适应倒计时
const SLOW_DIMENSIONS = new Set(['writing', 'speaking', 'listening'])
const questionTime = ref(30)
const timeLeft = ref(30)
let timerHandle: ReturnType<typeof setInterval> | null = null

function getQuestionTime(dim: string): number {
  return SLOW_DIMENSIONS.has(dim) ? 300 : 30
}

function startTimer() {
  stopTimer()
  timeLeft.value = questionTime.value
  timerHandle = setInterval(() => {
    timeLeft.value--
    if (timeLeft.value <= 0) {
      stopTimer()
      handleTimeout()
    }
  }, 1000)
}

function stopTimer() {
  if (timerHandle) { clearInterval(timerHandle); timerHandle = null }
}

function handleTimeout() {
  if (!currentQuestion.value || loading.value) return
  userAnswer.value = userAnswer.value || '(超时未作答)'
  submitAnswer()
}

onUnmounted(() => stopTimer())

watch(currentQuestion, (val) => {
  if (val && !loading.value) startTimer()
})

const timerPercent = computed(() => Math.round((timeLeft.value / questionTime.value) * 100))
const timerColor = computed(() => {
  if (timeLeft.value <= 10) return '#e53e3e'
  if (timeLeft.value <= 30) return '#f59e0b'
  return '#667eea'
})
const timerWidth = computed(() => {
  // 300s 题目在进度条上的等效宽度（归一化到30s视觉效果）
  if (questionTime.value > 30) return Math.round((timeLeft.value / questionTime.value) * 100)
  return Math.round((timeLeft.value / 30) * 100)
})

// 🔊 TTS 语音输出
const ttsPlaying = ref(false)
const ttsSupported = ref(typeof window !== 'undefined' && 'speechSynthesis' in window)

function playTTS(text: string) {
  if (!ttsSupported.value || !text) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = language.value === 'zh' ? 'zh-CN' : 'en-US'
  u.rate = 0.85
  u.pitch = 1.0
  u.onstart = () => { ttsPlaying.value = true }
  u.onend = () => { ttsPlaying.value = false }
  u.onerror = () => { ttsPlaying.value = false }
  window.speechSynthesis.speak(u)
}

function stopTTS() {
  window.speechSynthesis.cancel()
  ttsPlaying.value = false
}

// 🎤 语音输入 (SpeechRecognition)
const SpeechRecognitionAPI = (typeof window !== 'undefined'
  ? ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)
  : null) as typeof SpeechRecognition | null
const recording = ref(false)
const micSupported = ref(!!SpeechRecognitionAPI)
let recognition: any = null

function startRecording() {
  if (!SpeechRecognitionAPI) return
  stopTTS()
  const r = new SpeechRecognitionAPI()
  r.lang = language.value === 'zh' ? 'zh-CN' : 'en-US'
  r.interimResults = true
  r.continuous = true
  r.maxAlternatives = 1
  r.onresult = (e: any) => {
    let transcript = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      transcript += e.results[i][0].transcript
    }
    userAnswer.value = transcript
  }
  r.onerror = (e: any) => {
    console.warn('[Speech] error:', e.error)
    recording.value = false
  }
  r.onend = () => { recording.value = false }
  r.start()
  recognition = r
  recording.value = true
}

function stopRecording() {
  if (recognition) { recognition.stop(); recognition = null }
  recording.value = false
}

function reRecord() {
  stopRecording()
  userAnswer.value = ''
  setTimeout(() => startRecording(), 200)
}

// ── helpers ──
const TEXT_INPUT_TYPES = new Set([
  'fill_blank', 'writing', 'speaking', 'open_ended',
  'write_character', 'choose_character', 'identify_radical',
  'translation', 'correction', 'listening',
])

function detectType(raw: any, dim: string): string {
  if (raw.task_instruction) return dim === 'speaking' ? 'speaking' : 'writing'
  const t = raw.type || raw.question_type || 'multiple_choice'
  if (TEXT_INPUT_TYPES.has(t)) return t
  if (t === 'multiple_choice') return 'multiple_choice'
  if (raw.options?.length || raw.choices?.length) return 'multiple_choice'
  return 'fill_blank'
}

function detectQuestionText(raw: any): string {
  return raw.task_instruction || raw.question_text || raw.question || raw.text || raw.prompt || 'Loading...'
}

function isSubjective(type: string): boolean {
  return ['writing', 'speaking', 'open_ended'].includes(type)
}

function needsTextInput(type: string): boolean {
  return TEXT_INPUT_TYPES.has(type)
}

function rubricHtml(rubric: any): string {
  if (!rubric || typeof rubric !== 'object') return ''
  const lines: string[] = []
  for (const [key, val] of Object.entries(rubric)) {
    if (typeof val === 'object' && val !== null) {
      const v = val as any
      const pct = v.weight ? Math.round(v.weight * 100) + '%' : ''
      lines.push(`<strong>${key}</strong> <small>(${pct})</small>: ${v.criteria || ''}`)
    }
  }
  return lines.join('<br>')
}

// ── lifecycle ──
async function startAssessment() {
  error.value = ''; loading.value = true; lastFeedback.value = ''; feedbackKey.value++
  try {
    const user = JSON.parse(localStorage.getItem('lawa_user') || '{}')
    const res = await api.post('/assessment/start', { lang: language.value, user_id: user.id })
    assessmentId.value = res.data.assessment_id
    dimensions.value = res.data.dimensions || ['grammar', 'vocabulary', 'reading', 'writing']
    levelEstimate.value = res.data.current_level_estimate || 'B1'
    totalQuestions.value = res.data.total_questions_planned || 15
    started.value = true
    await loadNextQuestion()
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || 'Failed to start'
  } finally { loading.value = false }
}

async function loadNextQuestion() {
  stopTimer(); stopTTS(); stopRecording()
  error.value = ''; loading.value = true; lastFeedback.value = ''; feedbackKey.value++
  const dim = dimensions.value[previousResults.value.length % dimensions.value.length]
  try {
    const res = await api.post('/assessment/question', {
      assessment_id: assessmentId.value, lang: language.value, dimension: dim,
      current_level_estimate: levelEstimate.value, previous_results: previousResults.value,
    }, { timeout: SLOWER })
    const q = res.data.question || res.data
    const qType = detectType(q, dim)
    questionTime.value = getQuestionTime(dim)
    currentQuestion.value = {
      id: q.question_id || q.id || '',
      dimension: dim,
      question: detectQuestionText(q),
      type: qType,
      options: q.options || q.choices || [],
      correct_answer: q.correct_answer || q.answer || '',
      audio_text: q.audio_text || '',             // listening: 需朗读的文本
      rubric_html: rubricHtml(q.rubric),
      key_vocabulary: q.key_vocabulary || [],
      prompt_questions: q.prompt_questions || [],
      transcript_hint: q.transcript_hint || '',
      passage: q.passage || '',
      is_subjective: isSubjective(qType),
    }
    userAnswer.value = ''; selectedOption.value = ''
    startTimer()
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || 'Failed to load question'
  } finally { loading.value = false }
}

async function submitAnswer() {
  const q = currentQuestion.value
  if (!q) return
  const answer = needsTextInput(q.type) ? userAnswer.value : selectedOption.value
  if (!answer) return
  stopTimer(); stopTTS(); stopRecording()
  error.value = ''; loading.value = true
  try {
    const res = await api.post('/assessment/answer', {
      assessment_id: assessmentId.value, question_id: q.id, dimension: q.dimension,
      question_text: q.question, question_type: q.type, correct_answer: q.correct_answer || '',
      user_answer: answer, lang: language.value, current_level_estimate: levelEstimate.value,
    })
    const fb = res.data.feedback || (res.data.is_correct ? '✅ Correct!' : '❌ Incorrect')
    previousResults.value.push({
      dimension: q.dimension, question: q.question, user_answer: answer,
      correct_answer: q.correct_answer, is_correct: res.data.is_correct ?? true,
      score: res.data.score, feedback: fb,
    })
    lastFeedback.value = fb; feedbackKey.value++
    if (res.data.new_level_estimate) levelEstimate.value = res.data.new_level_estimate
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to submit'
    loading.value = false; startTimer()
    return
  }
  loading.value = false
  if (previousResults.value.length >= totalQuestions.value) await finishAssessment()
  else await loadNextQuestion()
}

async function finishAssessment() {
  loading.value = true; stopTimer()
  try {
    const res = await api.post('/assessment/report', {
      assessment_id: assessmentId.value, lang: language.value, all_answers: previousResults.value,
    })
    localStorage.setItem('lawa_report_last', JSON.stringify(res.data))
    router.push(`/assessment/${assessmentId.value}`)
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to generate report'; loading.value = false
  }
}

function progressPct() {
  if (totalQuestions.value === 0) return 0
  return Math.round((previousResults.value.length / totalQuestions.value) * 100)
}

// 显示标签
const showTimerLabel = computed(() => questionTime.value > 30)
</script>

<template>
  <div class="view-container">
    <h1>{{ t('assessment') }}</h1>
    <div v-if="!started" class="card">
      <p>{{ t('assessment_desc') }}</p>
      <div class="form-group">
        <label>{{ t('select_language') }}</label>
        <select v-model="language">
          <option value="en">English</option>
          <option value="zh">中文</option>
        </select>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn-primary" @click="startAssessment" :disabled="loading">
        {{ loading ? 'Loading...' : t('start') }}
      </button>
    </div>
    <div v-else>
      <div class="progress-bar"><div class="progress-fill" :style="{ width: progressPct() + '%' }"></div></div>
      <div class="timer-row">
        <div class="timer-bar-bg">
          <div class="timer-bar-fill" :style="{ width: timerWidth + '%', background: timerColor }"></div>
        </div>
        <span class="timer-text" :style="{ color: timerColor }">
          {{ timeLeft }}s
          <small v-if="showTimerLabel" class="timer-label">/ {{ questionTime }}s</small>
        </span>
      </div>
      <p class="dim-label">
        Q{{ previousResults.length + 1 }}/{{ totalQuestions }} &middot; {{ currentQuestion?.dimension }}
        <span v-if="currentQuestion?.is_subjective" class="subj-badge">subjective</span>
        <span v-if="questionTime > 30" class="time-badge">⏱ {{ questionTime }}s</span>
      </p>

      <div v-if="loading" class="card"><p class="loading-text">Loading question...</p></div>

      <div v-else-if="currentQuestion" class="card">
        <!-- 🔊 Listening: TTS 播放 -->
        <div v-if="currentQuestion.dimension === 'listening' && (currentQuestion.audio_text || currentQuestion.question)" class="tts-bar">
          <p class="tts-hint">👂 请听下面的内容，然后回答问题（可播放多次）</p>
          <button class="tts-btn" @click="playTTS(currentQuestion.audio_text || currentQuestion.question)" :disabled="ttsPlaying">
            {{ ttsPlaying ? '🔊 播放中...' : '🔈 播放音频' }}
          </button>
          <button v-if="ttsPlaying" class="tts-stop-btn" @click="stopTTS">⏹ 停止</button>
          <p v-if="currentQuestion.transcript_hint" class="transcript-hint">💡 关键词: {{ currentQuestion.transcript_hint }}</p>
        </div>

        <!-- Reading 文章 + 题目 -->
        <div v-if="currentQuestion.passage" class="reading-section">
          <div class="passage-box">
            <div class="passage-header">
              <p class="passage-label">📖 阅读材料</p>
              <span class="passage-word-count">{{ currentQuestion.passage.split(/\s+/).length }} words</span>
            </div>
            <div class="passage-text">{{ currentQuestion.passage }}</div>
          </div>
          <div class="reading-question-box">
            <p class="question-label">📝 问题</p>
            <p class="question-text">{{ currentQuestion.question }}</p>
          </div>
        </div>
        <p v-else class="question-text">{{ currentQuestion.question }}</p>

        <div v-if="currentQuestion.rubric_html" class="rubric-box" v-html="currentQuestion.rubric_html"></div>
        <div v-if="currentQuestion.key_vocabulary?.length" class="vocab-row">
          <span class="vocab-label">Key vocab:</span>
          <span v-for="w in currentQuestion.key_vocabulary" :key="w" class="vocab-chip">{{ w }}</span>
        </div>
        <div v-if="currentQuestion.prompt_questions?.length" class="prompt-list">
          <p class="prompt-label">Think about:</p>
          <ul><li v-for="pq in currentQuestion.prompt_questions" :key="pq">{{ pq }}</li></ul>
        </div>

        <!-- 选择题 -->
        <div v-if="currentQuestion.options?.length" class="options">
          <label v-for="opt in currentQuestion.options" :key="opt" class="option-item" :class="{ selected: selectedOption === opt }">
            <input type="radio" :value="opt" v-model="selectedOption" /> <span>{{ opt }}</span>
          </label>
        </div>

        <!-- 🎤 Speaking: 录音区 -->
        <div v-else-if="currentQuestion.dimension === 'speaking'" class="speaking-area">
          <div class="mic-row">
            <button v-if="!recording" class="mic-btn record" @click="startRecording" :disabled="!micSupported">
              🎤 开始录音
            </button>
            <button v-else class="mic-btn recording" @click="stopRecording">
              ⏹ 停止录音
            </button>
            <button v-if="userAnswer && !recording" class="mic-btn rerecord" @click="reRecord">
              🔄 重新录音
            </button>
          </div>
          <div v-if="recording" class="recording-indicator">
            <span class="pulse"></span> 正在录音中...
          </div>
          <textarea
            v-model="userAnswer"
            :placeholder="recording ? '语音识别中...' : '录音后此处显示识别文本，可手动修改'"
            :rows="6" class="answer-input"
          ></textarea>
          <p v-if="!micSupported" class="error">⚠️ 此浏览器不支持语音识别，请使用 Chrome 或手动输入</p>
        </div>

        <!-- 普通文本输入 -->
        <textarea
          v-else
          v-model="userAnswer"
          :placeholder="currentQuestion.is_subjective ? 'Write your response here...' : 'Type your answer...'"
          :rows="currentQuestion.is_subjective ? 6 : 3"
          class="answer-input"
        ></textarea>

        <div v-if="lastFeedback" :key="feedbackKey" class="feedback-box">{{ lastFeedback }}</div>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn-primary" @click="submitAnswer" :disabled="loading || (!selectedOption && !userAnswer)">
          {{ loading ? 'Submitting...' : previousResults.length + 1 >= totalQuestions ? 'Finish' : 'Next' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 720px; margin: 0 auto; padding: 24px; }
.card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-top: 16px; }
.progress-bar { background: #e9ecef; border-radius: 20px; height: 8px; margin-bottom: 4px; }
.progress-fill { background: #667eea; height: 100%; border-radius: 20px; transition: width .3s; }
/* ⏱️ */
.timer-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.timer-bar-bg { flex: 1; background: #e9ecef; border-radius: 6px; height: 6px; }
.timer-bar-fill { height: 100%; border-radius: 6px; transition: width 1s linear, background .3s; }
.timer-text { font-size: .8rem; font-weight: 600; min-width: 32px; text-align: right; white-space: nowrap; }
.timer-label { font-weight: 400; color: #999; font-size: .7rem; }
.dim-label { font-size: .85rem; color: #888; margin: 0 0 16px; }
.subj-badge { display: inline-block; background: #f0f0ff; color: #667eea; padding: 1px 8px; border-radius: 10px; font-size: .75rem; margin-left: 8px; }
.time-badge { display: inline-block; background: #fff3cd; color: #856404; padding: 1px 8px; border-radius: 10px; font-size: .75rem; margin-left: 8px; }
.loading-text { color: #999; text-align: center; padding: 24px 0; }
.form-group { margin-bottom: 16px; }
select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px; font-size: 1rem; }
/* Reading 文章 */
.reading-section { margin: 12px 0; }
.passage-box { background: #f8f9ff; border: 1px solid #d0d5f0; border-radius: 10px; padding: 16px; margin-bottom: 12px; }
.passage-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.passage-label { font-size: .8rem; color: #667eea; font-weight: 600; margin: 0; }
.passage-word-count { font-size: .75rem; color: #999; }
.passage-text { font-size: .95rem; line-height: 1.8; color: #444; white-space: pre-wrap; }
.reading-question-box { background: #fffdf0; border: 1px solid #f0e8b0; border-radius: 10px; padding: 14px; }
.question-label { font-size: .8rem; color: #b8860b; font-weight: 600; margin: 0 0 6px; }
.question-text { font-size: 1.1rem; margin: 16px 0; line-height: 1.6; white-space: pre-wrap; }
/* 🔊 TTS */
.tts-bar { background: #f0f4ff; border: 1px solid #c7d2fe; border-radius: 10px; padding: 14px; margin: 12px 0; }
.tts-hint { font-size: .85rem; color: #555; margin: 0 0 10px; }
.tts-btn { background: #667eea; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: .9rem; margin-right: 8px; }
.tts-btn:disabled { opacity: .6; }
.tts-stop-btn { background: #e53e3e; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: .9rem; }
.transcript-hint { font-size: .8rem; color: #888; margin: 8px 0 0; font-style: italic; }
/* 🎤 */
.speaking-area { margin: 12px 0; }
.mic-row { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.mic-btn { border: none; padding: 10px 18px; border-radius: 8px; cursor: pointer; font-size: .9rem; }
.mic-btn.record { background: #667eea; color: #fff; }
.mic-btn.recording { background: #e53e3e; color: #fff; animation: pulse-bg 1.5s infinite; }
.mic-btn.rerecord { background: #f59e0b; color: #fff; }
.mic-btn:disabled { opacity: .5; cursor: not-allowed; }
@keyframes pulse-bg { 0%,100% { opacity: 1; } 50% { opacity: .7; } }
.recording-indicator { display: flex; align-items: center; gap: 8px; color: #e53e3e; font-size: .85rem; margin-bottom: 6px; }
.pulse { width: 10px; height: 10px; background: #e53e3e; border-radius: 50%; animation: pulse-dot 1s infinite; }
@keyframes pulse-dot { 0%,100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.5); opacity: .5; } }
.rubric-box { background: #f8f9ff; border: 1px solid #d0d5f0; border-radius: 8px; padding: 12px; margin: 10px 0; font-size: .85rem; line-height: 1.5; color: #555; }
.rubric-box :deep(small) { color: #999; }
.vocab-row { margin: 8px 0 12px; }
.vocab-label { font-size: .8rem; color: #888; margin-right: 6px; }
.vocab-chip { display: inline-block; background: #e8ecff; color: #5566cc; padding: 2px 10px; border-radius: 14px; font-size: .8rem; margin: 2px 4px; }
.prompt-list { margin: 10px 0; background: #fffdf0; border: 1px solid #f0e8b0; border-radius: 8px; padding: 8px 16px; font-size: .85rem; }
.prompt-label { color: #888; margin: 0 0 4px; font-weight: 500; }
.prompt-list ul { margin: 4px 0; padding-left: 20px; }
.options { display: flex; flex-direction: column; gap: 8px; margin: 12px 0; }
.option-item { display: flex; align-items: center; gap: 8px; padding: 10px; border: 1px solid #e9ecef; border-radius: 8px; cursor: pointer; }
.option-item:hover, .option-item.selected { background: #f0f0ff; border-color: #667eea; }
.answer-input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 1rem; margin: 12px 0; box-sizing: border-box; min-height: 80px; resize: vertical; }
.feedback-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px; margin: 12px 0; font-size: .9rem; line-height: 1.5; white-space: pre-wrap; }
.btn-primary { width: 100%; background: #667eea; color: #fff; border: none; padding: 12px; border-radius: 8px; font-size: 1rem; cursor: pointer; margin-top: 12px; }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.error { color: #e53e3e; margin: 8px 0; font-size: .85rem; }
</style>
