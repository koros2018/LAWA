<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import api from '@/api'
import { t } from '@/i18n'

// t imported from @/i18n

const router = useRouter()

const title = ref('')
const description = ref('')
const taskType = ref('translation')
const languagePair = ref('en→zh')
const difficulty = ref(2)
const rewardCoin = ref(10)
const tags = ref('')
const deadline = ref('')
const generateAi = ref(false)
const sourceContent = ref('')
const aiDraft = ref('')
const loading = ref(false)
const error = ref('')

const taskTypes = ['translation','proofreading','summary','writing','speaking','tutoring','other']

async function generateDraft() {
  if (!sourceContent.value) return
  try {
    const res = await api.post('/tasks/ai-draft', {
      task_type: taskType.value,
      content: sourceContent.value,
    })
    aiDraft.value = res.data.draft || ''
  } catch { aiDraft.value = '(生成失败)' }
}

async function submit() {
  error.value = ''
  loading.value = true
  const user = JSON.parse(localStorage.getItem('lawa_user') || '{}')
  try {
    const res = await api.post('/tasks', {
      publisher_id: user.id || user.sub || 'anonymous',
      title: title.value,
      description: description.value,
      task_type: taskType.value,
      language_pair: languagePair.value || undefined,
      difficulty: difficulty.value,
      reward_coin: rewardCoin.value,
      tags: tags.value ? tags.value.split(',').map((t:string) => t.trim()) : [],
      deadline: deadline.value || undefined,
      generate_ai: generateAi.value,
      content: sourceContent.value || undefined,
    })
    router.push(`/tasks/${res.data.task.id}`)
  } catch (e: any) {
    error.value = e.response?.data?.detail || '发布失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="view-container">
    <div class="header-row">
      <h1>{{ t('publish_task') }}</h1>
      <router-link to="/tasks" class="btn-outline">← {{ t('tasks') }}</router-link>
    </div>

    <div class="form-card">
      <div class="form-group">
        <label>{{ t('task_title') }}</label>
        <input v-model="title" type="text" required maxlength="200" />
      </div>
      <div class="form-group">
        <label>{{ t('task_description') }}</label>
        <textarea v-model="description" rows="3"></textarea>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>{{ t('task_type') }}</label>
          <select v-model="taskType">
            <option v-for="t in taskTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>{{ t('language_pair') }}</label>
          <input v-model="languagePair" placeholder="en→zh" />
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>{{ t('difficulty') }} (1-5)</label>
          <input v-model.number="difficulty" type="number" min="1" max="5" />
        </div>
        <div class="form-group">
          <label>{{ t('reward_coin') }}</label>
          <input v-model.number="rewardCoin" type="number" min="0" />
        </div>
      </div>
      <div class="form-group">
        <label>{{ t('tags') }}</label>
        <input v-model="tags" :placeholder="t('tags_hint')" />
      </div>
      <div class="form-group">
        <label>{{ t('deadline') }}</label>
        <input v-model="deadline" type="datetime-local" />
      </div>

      <!-- AI 辅助 -->
      <div class="ai-section">
        <label class="checkbox">
          <input v-model="generateAi" type="checkbox" />
          {{ t('enable_ai_draft') }}
        </label>
        <div v-if="generateAi" class="ai-input-area">
          <textarea v-model="sourceContent" :placeholder="t('source_content')" rows="4"></textarea>
          <button @click="generateDraft" class="btn-secondary">🤖 {{ t('generate_draft') }}</button>
          <div v-if="aiDraft" class="ai-draft">
            <strong>AI 初稿：</strong>
            <p>{{ aiDraft }}</p>
          </div>
        </div>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
      <button @click="submit" :disabled="loading" class="btn-primary">
        {{ loading ? '...' : t('publish_task') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 640px; margin: 0 auto; padding: 24px; }
.header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.header-row h1 { margin: 0; }
.btn-outline { background: none; border: 1px solid var(--primary); color: var(--primary); padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: .85rem; }
.form-card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.form-group { margin-bottom: 16px; }
label { display: block; margin-bottom: 4px; font-weight: 500; font-size: .85rem; }
input, textarea, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px; font-size: .95rem; box-sizing: border-box; }
input:focus, textarea:focus { outline: none; border-color: var(--primary); }
.form-row { display: flex; gap: 16px; }
.form-row .form-group { flex: 1; }
.ai-section { background: #f0f4ff; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.checkbox { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.checkbox input { width: auto; }
.ai-input-area { margin-top: 12px; }
.btn-secondary { background: #6b7280; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; margin-top: 8px; font-size: .85rem; }
.ai-draft { background: white; border: 1px solid #e0e7ff; border-radius: 8px; padding: 12px; margin-top: 12px; font-size: .85rem; }
.ai-draft p { margin: 8px 0 0; color: #444; }
.btn-primary { background: var(--primary); color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 1rem; cursor: pointer; width: 100%; }
.btn-primary:disabled { opacity: .6; }
.error { color: #e53e3e; font-size: .85rem; margin: 8px 0; }
</style>
