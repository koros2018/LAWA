<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { t } from '@/i18n'
import TutorProfile from '@/components/TutorProfile.vue'
import TutorChat from '@/components/TutorChat.vue'
import TutorLesson from '@/components/TutorLesson.vue'
import TutorInsights from '@/components/TutorInsights.vue'
import TutorMarket from '@/components/TutorMarket.vue'

const user = ref<any>({})
const activeTab = ref('profile')
const lang = ref('en')

const tabList = [
  { key: 'profile', label: '🧠 Profile' },
  { key: 'chat', label: '💬 Chat' },
  { key: 'lesson', label: '📖 Lesson' },
  { key: 'insights', label: '📊 Insights' },
  { key: 'market', label: '🏪 Market' },
]

onMounted(() => {
  const u = localStorage.getItem('lawa_user')
  if (u) user.value = JSON.parse(u)
})

const userId = user.value?.id || ''
</script>

<template>
  <div class="view-container">
    <div class="header">
      <h1>🧠 {{ t('tutor') }}</h1>
      <select v-model="lang" class="lang-switch">
        <option value="en">English</option><option value="zh">中文</option>
      </select>
    </div>

    <div class="tabs">
      <button v-for="tb in tabList" :key="tb.key"
        :class="{ active: activeTab === tb.key }"
        @click="activeTab = tb.key">
        {{ tb.label }}
      </button>
    </div>

    <div class="tab-content">
      <TutorProfile v-if="activeTab==='profile'" :lang="lang" :userId="userId" />
      <TutorChat v-if="activeTab==='chat'" :lang="lang" :userId="userId" />
      <TutorLesson v-if="activeTab==='lesson'" :lang="lang" :userId="userId" />
      <TutorInsights v-if="activeTab==='insights'" :lang="lang" :userId="userId" />
      <TutorMarket v-if="activeTab==='market'" :lang="lang" :userId="userId" />
    </div>
  </div>
</template>

<style scoped>
.view-container { max-width: 800px; margin: 0 auto; padding: 24px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.header h1 { margin: 0; }
.lang-switch { padding: 6px 12px; border-radius: 8px; border: 1px solid #ddd; font-size: .85rem; }

.tabs { display: flex; gap: 4px; margin-bottom: 20px; flex-wrap: wrap; }
.tabs button { padding: 8px 18px; border: 1px solid #ddd; border-radius: 20px; background: #fff; cursor: pointer; font-size: .85rem; transition: all .15s; }
.tabs button.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.tab-content { min-height: 400px; }
</style>
