<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'

interface Provider {
  name: string
  model: string
  base_url: string
  is_default: boolean
  circuit_breaker: { failures: number; open: boolean; cooldown_remaining: number } | null
}

const providers = ref<Provider[]>([])
const status = ref<any>({})
const loading = ref(true)
const err = ref('')

// Add form
const showAdd = ref(false)
const showEdit = ref(false)
const editName = ref('')
const newProvider = ref({ name: '', api_key: '', base_url: '', model: '', provider_type: 'openai' })
const editProvider = ref({ name: '', api_key: '', base_url: '', model: '', provider_type: 'openai' })
const expandedProvider = ref<string | null>(null)

async function loadStatus() {
  loading.value = true; err.value = ''
  try {
    const [pr, st] = await Promise.all([
      api.get('/llm-config/list'),
      api.get('/llm-config/status'),
    ])
    providers.value = pr.data.providers || []
    status.value = st.data || {}
  } catch (e: any) { err.value = e.response?.data?.detail || 'Failed to load' }
  finally { loading.value = false }
}

async function addProvider() {
  if (!newProvider.value.api_key) { err.value = 'API Key required'; return }
  try {
    await api.post('/llm-config/add', newProvider.value)
    showAdd.value = false
    newProvider.value = { name: '', api_key: '', base_url: '', model: '', provider_type: 'openai' }
    await loadStatus()
  } catch (e: any) { err.value = e.response?.data?.detail || 'Add failed' }
}

async function testProvider(name: string) {
  try {
    const r = await api.post('/llm-config/test', { name })
    alert(`✅ ${name}: ${r.data.ping || 'Connected'}`)
  } catch (e: any) { alert(`❌ ${name}: ${e.response?.data?.detail || 'Failed'}`) }
}

async function removeProvider(name: string) {
  if (!confirm(`Delete provider "${name}"?`)) return
  try { await api.delete('/llm-config/remove', { data: { name } }); await loadStatus() }
  catch (e: any) { err.value = e.response?.data?.detail || 'Remove failed' }
}

function startEdit(p: Provider) {
  editName.value = p.name
  editProvider.value = { name: p.name, api_key: '', base_url: p.base_url, model: p.model, provider_type: 'openai' }
  showEdit.value = true
}

async function saveEdit() {
  if (!editProvider.value.base_url || !editProvider.value.model) { err.value = 'Base URL and Model required'; return }
  try {
    await api.put(`/llm-config/edit/${editName.value}`, editProvider.value)
    showEdit.value = false
    await loadStatus()
  } catch (e: any) { err.value = e.response?.data?.detail || 'Edit failed' }
}

function toggleExpand(name: string) {
  expandedProvider.value = expandedProvider.value === name ? null : name
}

async function setDefault(name: string) {
  try { await api.post('/llm-config/set-default', { name }); await loadStatus() }
  catch (e: any) { err.value = e.response?.data?.detail || 'Set default failed' }
}

onMounted(loadStatus)
</script>

<template>
  <div class="llm-page">
    <h2>🤖 云端大模型配置</h2>
    <p class="subtitle">管理 LAWA 连接的大模型 Provider</p>

    <p v-if="err" class="error">{{ err }}</p>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else>
      <!-- 状态总览 -->
      <div class="status-bar">
        <span>🏥 默认: <strong>{{ status.default_provider || 'none' }}</strong></span>
        <span>🔗 可用: <strong>{{ providers.length }}</strong></span>
        <span>🔌 熔断: <strong>{{ status.circuit_breaker_open_count || 0 }}</strong></span>
      </div>

      <!-- Provider 列表 -->
      <div class="provider-list">
        <div v-for="p in providers" :key="p.name" :class="['provider-card', { default: p.is_default }]">
          <div class="provider-header">
            <span class="provider-name">{{ p.name }}</span>
            <span v-if="p.is_default" class="badge-default">默认</span>
            <span v-if="p.circuit_breaker?.open" class="badge-breaker">🔌 熔断</span>
          </div>
          <div class="provider-meta">
            <div>📍 {{ p.base_url }}</div>
            <div>🧠 {{ p.model }}</div>
            <div v-if="p.circuit_breaker?.failures" class="breaker-info">
              失败: {{ p.circuit_breaker.failures }} 次
            </div>
          </div>
          <div class="provider-actions">
            <button class="btn-sm btn-test" @click="testProvider(p.name)">🧪 测试</button>
            <button class="btn-sm btn-edit" @click="startEdit(p)">✏️ 编辑</button>
            <button v-if="!p.is_default" class="btn-sm btn-set" @click="setDefault(p.name)">⭐ 设为默认</button>
            <button class="btn-sm btn-del" @click="removeProvider(p.name)">🗑 删除</button>
          </div>
        </div>
      </div>

      <!-- 添加 Provider -->
      <button v-if="!showAdd" class="btn-add" @click="showAdd = true">➕ 添加 Provider</button>
      <div v-else class="add-form card">
        <h4>添加新 Provider</h4>
        <div class="form-group">
          <label>名称</label>
          <input v-model="newProvider.name" placeholder="e.g. my-openai" />
        </div>
        <div class="form-group">
          <label>API Key</label>
          <input v-model="newProvider.api_key" type="password" placeholder="sk-..." />
        </div>
        <div class="form-group">
          <label>Base URL</label>
          <input v-model="newProvider.base_url" placeholder="https://api.openai.com/v1" />
        </div>
        <div class="form-group">
          <label>模型名</label>
          <input v-model="newProvider.model" placeholder="gpt-4o" />
        </div>
        <div class="form-actions">
          <button class="btn-primary" @click="addProvider">💾 保存</button>
          <button class="btn-cancel" @click="showAdd = false">取消</button>
        </div>
      </div>

      <!-- 编辑 Provider -->
      <div v-if="showEdit" class="add-form card">
        <h4>✏️ 编辑 Provider: {{ editName }}</h4>
        <div class="form-group">
          <label>API Key (留空保持不变)</label>
          <input v-model="editProvider.api_key" type="password" placeholder="sk-..." />
        </div>
        <div class="form-group">
          <label>Base URL</label>
          <input v-model="editProvider.base_url" placeholder="https://api.openai.com/v1" />
        </div>
        <div class="form-group">
          <label>模型名</label>
          <input v-model="editProvider.model" placeholder="gpt-4o" />
        </div>
        <div class="form-actions">
          <button class="btn-primary" @click="saveEdit">💾 保存修改</button>
          <button class="btn-cancel" @click="showEdit = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.llm-page { max-width: 800px; margin: 0 auto; padding: 24px; }
.subtitle { font-size: .85rem; color: #888; margin: 4px 0 20px; }
.status-bar { display: flex; gap: 20px; padding: 12px 16px; background: #f8f9ff; border-radius: 8px; font-size: .85rem; margin-bottom: 16px; }
.status-bar strong { color: #667eea; }
.provider-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.provider-card { background: white; border-radius: 10px; padding: 14px; border: 1px solid #e9ecef; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.provider-card.default { border-color: #667eea; background: #fafbff; }
.provider-header { display: flex; align-items: center; gap: 6px; }
.provider-name { font-weight: 600; font-size: .95rem; }
.badge-default { background: #667eea; color: #fff; padding: 1px 6px; border-radius: 4px; font-size: .7rem; }
.badge-breaker { background: #fee2e2; color: #dc2626; padding: 1px 6px; border-radius: 4px; font-size: .7rem; }
.provider-meta { font-size: .8rem; color: #666; }
.breaker-info { color: #dc2626; font-size: .75rem; }
.provider-actions { display: flex; gap: 6px; }
.btn-sm { padding: 4px 10px; border: 1px solid #ddd; border-radius: 6px; cursor: pointer; font-size: .78rem; background: white; }
.btn-test:hover { background: #f0fdf4; border-color: #86efac; }
.btn-edit:hover { background: #eff6ff; border-color: #93c5fd; }
.btn-set:hover { background: #fef9c3; border-color: #facc15; }
.btn-del:hover { background: #fee2e2; border-color: #fca5a5; color: #dc2626; }
.btn-add { background: #667eea; color: #fff; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: .9rem; }
.card { background: white; border-radius: 10px; padding: 20px; border: 1px solid #e9ecef; margin-top: 12px; }
.add-form h4 { margin: 0 0 12px; }
.form-group { margin-bottom: 10px; }
.form-group label { display: block; font-size: .8rem; color: #666; margin-bottom: 3px; }
.form-group input { width: 100%; padding: 8px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: .9rem; box-sizing: border-box; }
.form-actions { display: flex; gap: 8px; margin-top: 12px; }
.btn-primary { background: #667eea; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.btn-cancel { background: #f0f0f0; color: #666; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.loading { text-align: center; color: #888; padding: 40px; }
.error { color: #e53e3e; margin: 8px 0; font-size: .85rem; }
</style>
