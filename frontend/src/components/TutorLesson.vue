<script setup lang="ts">
import { ref } from 'vue'
import api from '@/api'

const props = defineProps<{ lang: string; userId: string }>()

const loadLesson = ref(false)
const lessonTopic = ref('')
const lessonResult = ref<any>(null)
const lessonFeedback = ref({ rating: 0, notes: '' })

function rateLesson(star: number) { lessonFeedback.value.rating = star }

async function doLesson() {
  loadLesson.value = true
  try {
    const res = await api.get('/tutor/lesson', { params: { user_id: props.userId, lang: props.lang, topic: lessonTopic.value } })
    lessonResult.value = res.data
  } catch { /* ignore */ } finally { loadLesson.value = false }
}
</script>

<template>
  <div class="card">
    <div class="lesson-input">
      <input v-model="lessonTopic" placeholder="Topic..." class="topic-inp" />
      <button @click="doLesson" :disabled="loadLesson" class="btn-primary">{{ loadLesson ? '🎓 ...' : '🎓 Generate Lesson' }}</button>
    </div>

    <div v-if="loadLesson" class="loading-spin">Loading...</div>

    <div v-if="lessonResult" class="lesson-card">
      <h3>📖 {{ lessonResult.title }}</h3>
      <p class="obj">{{ lessonResult.objective }}</p>
      <span class="time">⏱ {{ lessonResult.estimated_minutes }} min</span>

      <div class="section">
        <h4>🔥 Warm-up</h4>
        <div class="qbox" v-if="lessonResult.warm_up">
          <p>{{ lessonResult.warm_up.content }}</p>
          <details><summary>Answer</summary><code>{{ lessonResult.warm_up.expected_answer }}</code></details>
        </div>
      </div>

      <div class="section" v-if="lessonResult.core_lesson">
        <h4>📚 Core Lesson</h4>
        <p class="expl">{{ lessonResult.core_lesson.explanation }}</p>
        <div class="examples"><p v-for="ex in lessonResult.core_lesson.examples" :key="ex">💬 {{ ex }}</p></div>
        <div class="mistakes"><p v-for="m in lessonResult.core_lesson.common_mistakes" :key="m">⚠️ {{ m }}</p></div>
      </div>

      <div class="section" v-if="lessonResult.practice?.length">
        <h4>✏️ Practice</h4>
        <div v-for="(q,i) in lessonResult.practice" :key="i" class="qbox">
          <p class="qtype">{{ q.type }}</p>
          <p>{{ q.question }}</p>
          <details><summary>Answer</summary><code>{{ q.answer }}</code></details>
        </div>
      </div>

      <div class="section" v-if="lessonResult.challenge">
        <h4>🚀 Challenge</h4>
        <p><strong>{{ lessonResult.challenge.scenario }}</strong></p>
        <p>{{ lessonResult.challenge.task }}</p>
      </div>

      <div class="section" v-if="lessonResult.key_vocabulary?.length">
        <h4>📝 Key Vocabulary</h4>
        <div class="vocab-grid">
          <div v-for="v in lessonResult.key_vocabulary" :key="v.word" class="vocab-item">
            <strong>{{ v.word }}</strong> — {{ v.translation }}
            <small>{{ v.example }}</small>
          </div>
        </div>
      </div>

      <div v-if="lessonResult.tip" class="tip-box">💡 {{ lessonResult.tip }}</div>

      <div class="feedback-row">
        <div class="stars">
          <span v-for="s in 5" :key="s" @click="rateLesson(s)" :class="{on: lessonFeedback.rating >= s}">{{ s <= lessonFeedback.rating ? '⭐' : '☆' }}</span>
        </div>
        <input v-model="lessonFeedback.notes" placeholder="Notes..." class="fb-inp" />
        <button class="btn-small">Send</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card { background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.06); }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: .9rem; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-small { background: none; border: 1px solid var(--primary); color: var(--primary); padding: 4px 14px; border-radius: 6px; cursor: pointer; font-size: .8rem; }

.lesson-input { display: flex; gap: 10px; margin-bottom: 16px; }
.topic-inp { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 8px; font-size: .9rem; }

.lesson-card { margin-top: 16px; }
.lesson-card h3 { margin: 0 0 4px; }
.obj { color: #666; margin: 0 0 8px; font-size: .9rem; }
.time { display: inline-block; padding: 2px 10px; border-radius: 12px; background: #f0fdf4; color: #065f46; font-size: .78rem; font-weight: 600; }

.section { margin-top: 16px; padding: 12px; background: #f8fafc; border-radius: 8px; }
.section h4 { margin: 0 0 8px; }
.expl { line-height: 1.6; color: #334155; }
.examples p, .mistakes p { margin: 4px 0; font-size: .85rem; }
.mistakes p { color: #b91c1c; }

.qbox { padding: 10px; margin-bottom: 8px; background: #fff; border-radius: 6px; border: 1px solid #e2e8f0; }
.qbox .qtype { font-size: .7rem; color: #888; text-transform: uppercase; margin-bottom: 2px; }
.qbox details { margin-top: 6px; } .qbox code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: .85rem; }

.vocab-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }
.vocab-item { padding: 8px; background: #fff; border-radius: 6px; border: 1px solid #e2e8f0; }
.vocab-item strong { display: block; }
.vocab-item small { display: block; color: #888; margin-top: 2px; }

.tip-box { margin-top: 12px; padding: 12px; background: #fffbeb; border-radius: 8px; border: 1px solid #fde68a; }

.feedback-row { margin-top: 16px; display: flex; gap: 8px; align-items: center; }
.stars { display: flex; cursor: pointer; } .stars span { font-size: 1.2rem; }
.fb-inp { flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 6px; font-size: .85rem; }

.loading-spin { text-align: center; padding: 40px; color: #888; }
</style>
