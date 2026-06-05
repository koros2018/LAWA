<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'

const user = ref<any>({})
const loading = ref(true)

onMounted(async () => {
  try {
    const u = JSON.parse(localStorage.getItem('lawa_user') || '{}')
    const res = await api.get(`/auth/profile?user_id=${u.id}`)
    user.value = res.data.user || u
  } catch (e) {
    user.value = JSON.parse(localStorage.getItem('lawa_user') || '{}')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="profile-page">
    <h2>👤 个人资料</h2>
    <p v-if="loading">加载中...</p>
    <div v-else class="profile-card">
      <div class="profile-avatar">{{ user.username?.[0]?.toUpperCase() || '?' }}</div>
      <div class="profile-info">
        <div class="info-row"><span class="label">用户名</span><span>{{ user.username || '-' }}</span></div>
        <div class="info-row"><span class="label">邮箱</span><span>{{ user.email || '-' }}</span></div>
        <div class="info-row"><span class="label">等级</span><span>Lv.{{ user.level || 1 }}</span></div>
        <div class="info-row"><span class="label">经验</span><span>{{ user.xp || 0 }} XP</span></div>
        <div class="info-row"><span class="label">金币</span><span>{{ user.coins || 0 }} 🪙</span></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-page { max-width: 500px; margin: 0 auto; padding: 24px; }
.profile-card { background: white; border-radius: 14px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }
.profile-avatar { width: 72px; height: 72px; border-radius: 50%; background: linear-gradient(135deg, #667eea, #764ba2); color: white; font-size: 2rem; font-weight: 700; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; }
.profile-info { text-align: left; }
.info-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.label { color: #888; font-size: 0.85rem; }
</style>
