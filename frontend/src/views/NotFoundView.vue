<script setup lang="ts">import { t } from '@/i18n'

// t imported from @/i18n


</script>
<template>
  <div class="nf">
    <div class="nf-box">
      <div class="nf-icon">🦝</div>
      <h1>404</h1>
      <p>{{ t('page_not_found') }}</p>
      <router-link to="/dashboard" class="btn-primary">{{ t('back_home') }}</router-link>
    </div>
  </div>
</template>
<style scoped>
.nf { display: flex; justify-content: center; align-items: center; min-height: 70vh; }
.nf-box { text-align: center; }
.nf-icon { font-size: 5rem; margin-bottom: 16px; }
h1 { font-size: 4rem; margin: 0; color: var(--primary); }
p { color: #888; margin: 12px 0 24px; }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 12px 24px; border-radius: 8px; text-decoration: none; display: inline-block; }
</style>
