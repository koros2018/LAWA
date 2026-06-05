<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import api from '@/api'
import { t } from '@/i18n'

// t imported from @/i18n

const router = useRouter()
const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

async function register() {
  error.value = ''
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }
  loading.value = true
  try {
    const res = await api.post('/auth/register', {
      username: username.value,
      email: email.value,
      password: password.value,
    })
    localStorage.setItem('lawa_token', res.data.access_token)
    localStorage.setItem('lawa_user', JSON.stringify({ id: res.data.user_id, username: username.value }))
    router.push('/dashboard')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Registration failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-container">
    <div class="auth-card">
      <div class="auth-logo">🦝 LAWA</div>
      <h1>{{ t('register_title') }}</h1>
      <p class="subtitle">{{ t('register_subtitle') }}</p>
      <form @submit.prevent="register">
        <div class="form-group">
          <label>{{ t('username') }}</label>
          <input v-model="username" type="text" required />
        </div>
        <div class="form-group">
          <label>{{ t('email') }}</label>
          <input v-model="email" type="email" required />
        </div>
        <div class="form-group">
          <label>{{ t('password') }}</label>
          <input v-model="password" type="password" required />
        </div>
        <div class="form-group">
          <label>{{ t('confirm_password') }}</label>
          <input v-model="confirmPassword" type="password" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="loading">
          {{ loading ? '...' : t('register_button') }}
        </button>
      </form>
      <p class="switch-link">
        <router-link to="/login">{{ t('back_to_login') }}</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-container {
  display: flex; justify-content: center; align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.auth-card {
  background: white; border-radius: 16px; padding: 40px;
  width: 100%; max-width: 400px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.auth-logo { font-size: 2rem; text-align: center; margin-bottom: 8px; }
h1 { text-align: center; margin: 0 0 4px; }
.subtitle { text-align: center; color: #666; margin-bottom: 24px; font-size: 0.9rem; }
.form-group { margin-bottom: 16px; }
label { display: block; margin-bottom: 4px; font-weight: 500; font-size: 0.9rem; }
input { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 1rem; box-sizing: border-box; }
input:focus { outline: none; border-color: #667eea; }
.error { color: #e53e3e; font-size: 0.85rem; margin: 8px 0; }
button { width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.switch-link { text-align: center; margin-top: 16px; font-size: 0.85rem; }
.switch-link a { color: #667eea; }
</style>
