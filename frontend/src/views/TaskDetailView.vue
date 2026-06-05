<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '@/api'
import { t } from '@/i18n'

// t imported from @/i18n

const route = useRoute()
const router = useRouter()
const taskId = route.params.id as string
const task = ref<any>(null)
const loading = ref(true)

// Accept / Submit / Complete / Review
const submitContent = ref('')
const reviewRating = ref(5)
const reviewComment = ref('')
const actionLoading = ref(false)
const actionError = ref('')
const user = ref<any>({})

onMounted(async () => {
  const u = localStorage.getItem('lawa_user')
  if (u) user.value = JSON.parse(u)
  try {
    const res = await api.get(`/tasks/${taskId}`)
    task.value = res.data.task
  } catch { /* 404 */ }
  finally { loading.value = false }
})

function canAccept() {
  return task.value?.status === 'open' && task.value?.publisher_id !== (user.value.id || user.value.sub)
}
function canSubmit() { return task.value?.status === 'assigned' && task.value?.assignee_id === (user.value.id || user.value.sub) }
function canComplete() { return task.value?.status === 'submitted' && task.value?.publisher_id === (user.value.id || user.value.sub) }
function canReview() { return task.value?.status === 'completed' && [task.value.publisher_id, task.value.assignee_id].includes(user.value.id || user.value.sub) }

async function acceptTask() {
  actionLoading.value = true; actionError.value = ''
  try {
    const res = await api.post(`/tasks/${taskId}/accept`, { task_id: taskId, user_id: user.value.id || user.value.sub })
    task.value = res.data.task
  } catch (e: any) { actionError.value = e.response?.data?.detail || '操作失败' }
  finally { actionLoading.value = false }
}

async function submitTask() {
  if (!submitContent.value.trim()) return
  actionLoading.value = true; actionError.value = ''
  try {
    const res = await api.post(`/tasks/${taskId}/submit`, {
      task_id: taskId, user_id: user.value.id || user.value.sub,
      content: submitContent.value,
    })
    task.value = res.data.task
    submitContent.value = ''
  } catch (e: any) { actionError.value = e.response?.data?.detail || '操作失败' }
  finally { actionLoading.value = false }
}

async function completeTask() {
  actionLoading.value = true; actionError.value = ''
  try {
    const res = await api.post(`/tasks/${taskId}/complete`, { task_id: taskId, user_id: user.value.id || user.value.sub })
    task.value = res.data.task
  } catch (e: any) { actionError.value = e.response?.data?.detail || '操作失败' }
  finally { actionLoading.value = false }
}

async function reviewTask() {
  actionLoading.value = true; actionError.value = ''
  try {
    await api.post(`/tasks/${taskId}/review`, {
      task_id: taskId, user_id: user.value.id || user.value.sub,
      rating: reviewRating.value, comment: reviewComment.value,
    })
    alert('评价提交成功！')
  } catch (e: any) { actionError.value = e.response?.data?.detail || '操作失败' }
  finally { actionLoading.value = false }
}

function typeLabel(t: string) {
  const m: Record<string,string> = { translation:'翻译', proofreading:'润色', summary:'摘要', writing:'写作', speaking:'口语', tutoring:'辅导', other:'其他' }
  return m[t] || t
}

function statusLabel(s: string) {
  const m: Record<string,string> = { open:'待接单', assigned:'已接单', submitted:'待验收', completed:'已完成', cancelled:'已取消' }
  return m[s] || s
}
</script>

<template>
  <div class="view-container">
    <router-link to="/tasks" class="back-link">← {{ t('tasks') }}</router-link>
    <div v-if="loading">{{ t('loading') }}</div>
    <div v-else-if="task" class="detail">
      <div class="card">
        <div class="detail-header">
          <h1>{{ task.title }}</h1>
          <span :class="['status-badge', task.status]">{{ statusLabel(task.status) }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-item">📌 {{ typeLabel(task.task_type) }}</span>
          <span v-if="task.language_pair" class="meta-item">🌐 {{ task.language_pair }}</span>
          <span class="meta-item">🪙 {{ task.reward_coin || 0 }}</span>
          <span v-if="task.difficulty" class="meta-item">🔥 {{ task.difficulty }}/5</span>
        </div>
        <p v-if="task.description" class="desc">{{ task.description }}</p>

        <div v-if="task.ai_draft" class="ai-draft-section">
          <strong>🤖 AI 初稿：</strong>
          <p>{{ task.ai_draft }}</p>
        </div>

        <div class="submissions-section" v-if="task.submissions?.length">
          <h3>📤 {{ t('submissions') }}</h3>
          <div v-for="(s, i) in task.submissions" :key="s.id || i" class="submission-card">
            <p>{{ s.content }}</p>
            <span v-if="s.is_ai_assisted" class="ai-badge">AI辅助</span>
          </div>
        </div>

        <div class="reviews-section" v-if="task.reviews?.length">
          <h3>⭐ {{ t('reviews') }}</h3>
          <div v-for="(r, i) in task.reviews" :key="r.id || i" class="review-item">
            <span class="stars">{'⭐'.repeat(r.rating || 0)}</span>
            <p v-if="r.comment">{{ r.comment }}</p>
          </div>
        </div>
      </div>

      <!-- 操作面板 -->
      <div class="actions card">
        <button v-if="canAccept()" @click="acceptTask" :disabled="actionLoading" class="btn-primary btn-block">🤝 {{ t('accept_task') }}</button>
        <div v-if="canSubmit()">
          <textarea v-model="submitContent" :placeholder="t('submit_hint')" rows="4"></textarea>
          <button @click="submitTask" :disabled="actionLoading" class="btn-primary btn-block">📤 {{ t('submit_task') }}</button>
        </div>
        <button v-if="canComplete()" @click="completeTask" :disabled="actionLoading" class="btn-success btn-block">✅ {{ t('complete_task') }}</button>
        <div v-if="canReview()">
          <div class="star-input">
            <label v-for="s in 5" :key="s" class="star" @click="reviewRating = s">{{ s <= reviewRating ? '⭐' : '☆' }}</label>
          </div>
          <input v-model="reviewComment" :placeholder="t('review_hint')" />
          <button @click="reviewTask" :disabled="actionLoading" class="btn-secondary btn-block">⭐ {{ t('submit_review') }}</button>
        </div>
        <p v-if="actionError" class="error">{{ actionError }}</p>
      </div>
    </div>
    <div v-else class="not-found">
      <p>{{ t('task_not_found') }}</p>
      <router-link to="/tasks" class="btn-primary">← {{ t('tasks') }}</router-link>
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 720px; margin: 0 auto; padding: 24px; }
.back-link { color: var(--primary); text-decoration: none; display: inline-block; margin-bottom: 16px; font-size: .9rem; }
.card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 16px; }
.detail-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.detail-header h1 { margin: 0; font-size: 1.4rem; flex: 1; }
.status-badge { padding: 4px 12px; border-radius: 12px; font-size: .8rem; font-weight: 600; white-space: nowrap; }
.open { background: #dbeafe; color: #1e40af; }
.assigned { background: #fef3c7; color: #92400e; }
.submitted { background: #e0e7ff; color: #3730a3; }
.completed { background: #d1fae5; color: #065f46; }
.meta-row { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 12px; }
.meta-item { font-size: .85rem; color: #666; }
.desc { color: #444; line-height: 1.6; }
.ai-draft-section { background: #f0f4ff; border-radius: 8px; padding: 16px; margin: 16px 0; }
.ai-draft-section p { margin: 8px 0 0; color: #555; }
.submission-card { background: #f9fafb; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
.submission-card p { margin: 0 0 4px; }
.ai-badge { font-size: .75rem; background: #eef2ff; color: var(--primary); padding: 2px 6px; border-radius: 4px; }
.review-item { padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.review-item p { margin: 4px 0 0; color: #666; font-size: .85rem; }
.actions { display: flex; flex-direction: column; gap: 12px; }
.btn-primary { background: var(--primary); color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-size: .95rem; }
.btn-success { background: #059669; color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-size: .95rem; }
.btn-secondary { background: #6b7280; color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-size: .95rem; }
.btn-block { width: 100%; }
.actions textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }
.actions input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }
.actions button:disabled { opacity: .6; cursor: not-allowed; }
.star-input { display: flex; gap: 4px; }
.star { cursor: pointer; font-size: 1.5rem; }
.error { color: #e53e3e; font-size: .85rem; }
.not-found { text-align: center; padding: 60px; color: #888; }
</style>
