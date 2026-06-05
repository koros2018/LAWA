<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function login() {
  error.value = ''
  loading.value = true
  try {
    const res = await api.post('/auth/login', { username: username.value, password: password.value })
    localStorage.setItem('lawa_token', res.data.access_token)
    localStorage.setItem('lawa_user', JSON.stringify({ id: res.data.user_id, username: username.value }))
    router.push('/dashboard')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="display:flex;justify-content:center;align-items:center;min-height:100vh;background:linear-gradient(135deg,#667eea,#764ba2)">
    <div style="background:white;border-radius:16px;padding:40px;width:100%;max-width:400px;box-shadow:0 20px 60px rgba(0,0,0,.2)">
      <div style="font-size:2rem;text-align:center;margin-bottom:8px">🦝 LAWA</div>
      <h1 style="text-align:center;margin:0">Welcome to LAWA</h1>
      <p style="text-align:center;color:#666;margin-bottom:24px">Learn languages through real-world tasks</p>
      <form @submit.prevent="login">
        <div style="margin-bottom:16px">
          <label style="display:block;margin-bottom:4px;font-weight:500">Username</label>
          <input v-model="username" type="text" required style="width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:8px;font-size:1rem;box-sizing:border-box" />
        </div>
        <div style="margin-bottom:16px">
          <label style="display:block;margin-bottom:4px;font-weight:500">Password</label>
          <input v-model="password" type="password" required style="width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:8px;font-size:1rem;box-sizing:border-box" />
        </div>
        <p v-if="error" style="color:#e53e3e;font-size:.85rem;margin:8px 0">{{ error }}</p>
        <button type="submit" :disabled="loading" style="width:100%;padding:12px;background:#667eea;color:white;border:none;border-radius:8px;font-size:1rem;cursor:pointer">
          {{ loading ? '...' : 'Login' }}
        </button>
      </form>
    </div>
  </div>
</template>
