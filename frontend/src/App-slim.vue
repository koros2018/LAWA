<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isAuth = computed(() => !['login','register'].includes(route.name as string))
</script>

<template>
  <div id="app-shell">
    <aside v-if="isAuth" style="width:200px;background:white;padding:16px">
      <h2>🦝 LAWA</h2>
    </aside>
    <main :style="{ marginLeft: isAuth ? '200px' : '0', flex: 1 }">
      <router-view />
    </main>
  </div>
</template>

<style>
:root { --primary: #667eea; --sidebar-width: 200px; --bg: #f5f7fa; }
* { box-sizing: border-box; margin: 0; }
body { font-family: -apple-system, sans-serif; background: #f5f7fa; color: #333; min-height: 100vh; }
#app { min-height: 100vh; }
</style>
