<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

// ── 忘记密码 ──
const showForgot = ref(false)
const forgotUsername = ref('')
const forgotLoading = ref(false)
const forgotMessage = ref('')
const forgotError = ref('')
const resetToken = ref('')
const newPassword = ref('')
const showReset = ref(false)

async function login() {
  error.value = ''
  loading.value = true
  try {
    const res = await api.post('/auth/login', { username: username.value, password: password.value })
    localStorage.setItem('lawa_token', res.data.access_token)
    localStorage.setItem('lawa_user', JSON.stringify({ id: res.data.user_id, username: username.value }))
    router.push('/dashboard')
  } catch (e: any) { error.value = e.response?.data?.detail || 'Login failed' }
  finally { loading.value = false }
}

async function forgotPassword() {
  forgotError.value = ''
  forgotMessage.value = ''
  forgotLoading.value = true
  try {
    const res = await api.post('/auth/forgot-password', { username: forgotUsername.value })
    forgotMessage.value = res.data.message
    if (res.data.reset_token) {
      resetToken.value = res.data.reset_token
      showReset.value = true
    }
  } catch (e: any) { forgotError.value = e.response?.data?.detail || 'Request failed' }
  finally { forgotLoading.value = false }
}

async function resetPassword() {
  forgotError.value = ''
  forgotMessage.value = ''
  forgotLoading.value = true
  try {
    const res = await api.post('/auth/reset-password', { token: resetToken.value, new_password: newPassword.value })
    forgotMessage.value = res.data.message
    showReset.value = false
    showForgot.value = false
  } catch (e: any) { forgotError.value = e.response?.data?.detail || 'Reset failed' }
  finally { forgotLoading.value = false }
}
</script>

<template>
  <div class="auth-container"><div class="auth-card">
    <div class="auth-logo">🦝 LAWA</div>
    <h1>Welcome to LAWA</h1>
    <p class="subtitle">Learn languages through real-world tasks</p>
    <form @submit.prevent="login">
      <div class="form-group"><label>Username</label><input v-model="username" type="text" required /></div>
      <div class="form-group"><label>Password</label><input v-model="password" type="password" required /></div>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="loading">{{ loading ? '...' : 'Login' }}</button>
    </form>
    <p class="switch-link">Don't have an account? <router-link to="/register">Register</router-link></p>

    <!-- ── 忘记密码 ── -->
    <div class="forgot-section">
      <button type="button" class="link-btn" @click="showForgot = !showForgot">
        {{ showForgot ? '← Back to login' : 'Forgot password?' }}
      </button>

      <div v-if="showForgot && !showReset" class="forgot-form">
        <div class="form-group">
          <label>Username</label>
          <input v-model="forgotUsername" type="text" placeholder="Enter your username" />
        </div>
        <p v-if="forgotError" class="error">{{ forgotError }}</p>
        <p v-if="forgotMessage" class="success">{{ forgotMessage }}</p>
        <button type="button" class="btn-secondary" :disabled="forgotLoading || !forgotUsername.trim()" @click="forgotPassword">
          {{ forgotLoading ? '...' : 'Send Reset Link' }}
        </button>
      </div>

      <div v-if="showReset" class="forgot-form">
        <p class="hint">Paste the reset token and set a new password:</p>
        <div class="form-group">
          <label>Reset Token</label>
          <input v-model="resetToken" type="text" placeholder="Paste token here" />
        </div>
        <div class="form-group">
          <label>New Password</label>
          <input v-model="newPassword" type="password" placeholder="Min 6 characters" />
        </div>
        <p v-if="forgotError" class="error">{{ forgotError }}</p>
        <p v-if="forgotMessage" class="success">{{ forgotMessage }}</p>
        <button type="button" class="btn-secondary" :disabled="forgotLoading || !resetToken.trim() || newPassword.length < 6" @click="resetPassword">
          {{ forgotLoading ? '...' : 'Reset Password' }}
        </button>
      </div>
    </div>
  </div></div>
</template>

<style scoped>
.auth-container{display:flex;justify-content:center;align-items:center;min-height:100vh;background:linear-gradient(135deg,#667eea,#764ba2)}
.auth-card{background:white;border-radius:16px;padding:40px;max-width:400px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.2)}
.auth-logo{font-size:2rem;text-align:center;margin-bottom:8px}
h1{text-align:center;margin:0 0 4px}
.subtitle{text-align:center;color:#666;margin-bottom:24px;font-size:.9rem}
.form-group{margin-bottom:16px}
label{display:block;margin-bottom:4px;font-weight:500;font-size:.9rem}
input{width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:8px;font-size:1rem;box-sizing:border-box}
input:focus{outline:none;border-color:#667eea}
.error{color:#e53e3e;font-size:.85rem;margin:8px 0}
button{width:100%;padding:12px;background:#667eea;color:white;border:none;border-radius:8px;font-size:1rem;cursor:pointer}
button:disabled{opacity:.6;cursor:not-allowed}
.switch-link{text-align:center;margin-top:16px;font-size:.85rem}
.switch-link a{color:#667eea}

/* ── Forgot Password ── */
.forgot-section{margin-top:20px;padding-top:16px;border-top:1px solid #eee}
.link-btn{background:none;border:none;color:#667eea;cursor:pointer;font-size:.85rem;padding:0}
.link-btn:hover{text-decoration:underline}
.forgot-form{margin-top:12px}
.forgot-form .form-group{margin-bottom:10px}
.forgot-form label{font-size:.8rem}
.forgot-form input{padding:8px 10px;font-size:.85rem}
.btn-secondary{width:100%;padding:10px;background:#f1f5f9;color:#333;border:1px solid #ddd;border-radius:8px;font-size:.9rem;cursor:pointer;margin-top:8px}
.btn-secondary:disabled{opacity:.5;cursor:not-allowed}
.hint{font-size:.8rem;color:#666;margin:0 0 8px}
.success{color:#059669;font-size:.85rem;margin:8px 0}
</style>
