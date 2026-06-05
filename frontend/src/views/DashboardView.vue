<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'

const user = ref<any>({})
const loading = ref(true)

onMounted(async () => {
  try {
    const u = localStorage.getItem('lawa_user')
    if (u) user.value = JSON.parse(u)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="dashboard" v-if="!loading">
    <h2>👋 Hello, {{ user.username || 'Learner' }}!</h2>
    <p>Dashboard works!</p>
    <nav>
      <router-link to="/assessment">Assessment</router-link> |
      <router-link to="/tasks">Tasks</router-link> |
      <router-link to="/world">World Map</router-link>
    </nav>
  </div>
  <div v-else class="loading">Loading...</div>
</template>

<style scoped>
.dashboard { padding: 20px; }
.loading { text-align: center; padding: 60px; }
</style>
