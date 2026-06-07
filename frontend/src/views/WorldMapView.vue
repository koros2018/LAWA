<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'

interface Zone {
  id: string
  code: string
  name: string
  culture_theme: string
  native_lang: string
  map_position: { x: number, y: number }
}

interface ZoneNode {
  id: string
  code: string
  name: string
  node_type: string
  skill_focus: string
  cefr_min: string
  cefr_max: string
  daily_quest_pool: string[]
  npc_dialogue: Record<string, string>
  description: string
}

const zones = ref<Zone[]>([])
const selectedZone = ref<Zone | null>(null)
const nodes = ref<ZoneNode[]>([])
const selectedNode = ref<ZoneNode | null>(null)
const loading = ref(true)
const traveling = ref(false)

const nodeTypeIcon: Record<string, string> = {
  academy: '🏫',
  city: '🏙️',
  dungeon: '⚔️',
  market: '🏪',
}

const skillIcon: Record<string, string> = {
  grammar: '📖',
  reading: '📕',
  writing: '✍️',
  speaking: '💬',
}

onMounted(async () => {
  try {
    const res = await api.get('/rpg/world/zones')
    zones.value = res.data.zones || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

async function selectZone(zone: Zone) {
  selectedZone.value = zone
  selectedNode.value = null
  try {
    const res = await api.get(`/rpg/world/zones/${zone.code}`)
    nodes.value = res.data.nodes || []
  } catch (e) {
    console.error(e)
    nodes.value = []
  }
}

function selectNode(node: ZoneNode) {
  selectedNode.value = node
}

async function travel(zoneCode: string) {
  const u = JSON.parse(localStorage.getItem('lawa_user') || '{}')
  const token = localStorage.getItem('lawa_token')
  if (!u?.id || !token) {
    ElMessage.warning('请先登录')
    return
  }
  traveling.value = true
  try {
    await api.post('/rpg/world/travel', { user_id: u.id, target_zone_code: zoneCode })
    ElMessage.success(`🚀 已前往 ${zoneCode} 区域`)
  } catch (e: any) {
    const msg = e.response?.data?.detail || e.message || '未知错误'
    ElMessage.error(`进入场景失败: ${msg}`)
  } finally {
    traveling.value = false
  }
}
</script>

<template>
  <div class="world-map" v-if="!loading">
    <h2>🌍 LAWA 世界地图</h2>

    <!-- 区域卡片 -->
    <div class="zones-grid">
      <div
        v-for="zone in zones"
        :key="zone.id"
        :class="['zone-card', { active: selectedZone?.id === zone.id }]"
        @click="selectZone(zone)"
      >
        <div class="zone-header">
          <span class="zone-flag">{{ zone.code === 'zh-cn' ? '🏯' : '🏰' }}</span>
          <span class="zone-name">{{ zone.name }}</span>
        </div>
        <div class="zone-theme">{{ zone.culture_theme }}</div>
        <div class="zone-lang">{{ zone.native_lang === 'zh' ? '中文区' : 'English Zone' }}</div>
        <button class="travel-btn" :disabled="traveling" @click.stop="travel(zone.code)">
          {{ traveling ? '✈️ 前往中...' : '✈️ 前往' }}
        </button>
      </div>
    </div>

    <!-- 选中区域的场景节点 -->
    <div v-if="selectedZone" class="zone-detail">
      <h3>{{ selectedZone.code === 'zh-cn' ? '🏯' : '🏰' }} {{ selectedZone.name }} — 场景</h3>
      <div class="nodes-grid">
        <div
          v-for="node in nodes"
          :key="node.id"
          :class="['node-card', { active: selectedNode?.id === node.id }]"
          @click="selectNode(node)"
        >
          <div class="node-icon">{{ nodeTypeIcon[node.node_type] || '📍' }}</div>
          <div class="node-name">{{ node.name }}</div>
          <div class="node-type">{{ node.node_type }}</div>
          <div class="node-skill" v-if="node.skill_focus">
            {{ skillIcon[node.skill_focus] || '📌' }} {{ node.skill_focus }}
          </div>
          <div class="node-level">
            {{ node.cefr_min }} ~ {{ node.cefr_max }}
          </div>
        </div>
      </div>
    </div>

    <!-- 选中节点的详情 -->
    <div v-if="selectedNode" class="node-detail-panel">
      <div class="detail-header">
        <h4>{{ nodeTypeIcon[selectedNode.node_type] }} {{ selectedNode.name }}</h4>
        <span class="detail-badge">{{ selectedNode.node_type }}</span>
      </div>
      <p v-if="selectedNode.description" class="detail-desc">{{ selectedNode.description }}</p>
      <div class="detail-grid">
        <div class="detail-item">
          <span class="detail-label">🎯 技能</span>
          <span class="detail-value">{{ skillIcon[selectedNode.skill_focus] || '📌' }} {{ selectedNode.skill_focus }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">📊 推荐等级</span>
          <span class="detail-value">{{ selectedNode.cefr_min }} ~ {{ selectedNode.cefr_max }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">📋 任务数</span>
          <span class="detail-value">{{ (selectedNode.daily_quest_pool || []).length }} 个</span>
        </div>
      </div>

      <!-- NPC 对话 -->
      <div v-if="Object.keys(selectedNode.npc_dialogue || {}).length" class="npc-section">
        <h5>💬 NPC 对话</h5>
        <div class="npc-list">
          <div v-for="(npc, dialog) in selectedNode.npc_dialogue" :key="npc" class="npc-item">
            <span class="npc-name">🧙 {{ npc }}</span>
            <span class="npc-dialog">{{ dialog }}</span>
          </div>
        </div>
      </div>

      <!-- 任务池 -->
      <div v-if="(selectedNode.daily_quest_pool || []).length" class="quest-section">
        <h5>📋 可用任务</h5>
        <ul class="quest-list">
          <li v-for="(q, i) in selectedNode.daily_quest_pool" :key="i">{{ q }}</li>
        </ul>
      </div>

      <button class="enter-btn" :disabled="traveling" @click="travel(selectedZone!.code)">
        {{ traveling ? '🚀 前往中...' : '🚀 进入场景' }}
      </button>
    </div>
  </div>
  <div v-else class="loading">加载中...</div>
</template>

<style scoped>
.world-map { padding: 20px; max-width: 900px; margin: 0 auto; }
.world-map h2 { margin-bottom: 20px; }
.zone-name { font-size: 1.1rem; }

/* 区域卡片 */
.zones-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 24px; }
.zone-card {
  background: white;
  border-radius: 14px;
  padding: 20px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  border: 2px solid transparent;
  transition: all 0.2s;
}
.zone-card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.12); }
.zone-card.active { border-color: #3b82f6; }
.zone-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.zone-flag { font-size: 2rem; }
.zone-theme { font-size: 0.85rem; color: #6b7280; margin-bottom: 4px; }
.zone-lang { font-size: 0.8rem; color: #9ca3af; margin-bottom: 12px; }
.travel-btn {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 6px 16px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: opacity 0.2s;
}
.travel-btn:hover { opacity: 0.9; }

/* 场景节点 */
.zone-detail { margin-bottom: 20px; }
.zone-detail h3 { margin-bottom: 12px; }
.nodes-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
.node-card {
  background: white;
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  text-align: center;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  border: 2px solid transparent;
  transition: all 0.2s;
}
.node-card:hover { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.node-card.active { border-color: #f59e0b; background: #fffbeb; }
.node-icon { font-size: 1.5rem; margin-bottom: 4px; }
.node-name { font-size: 0.9rem; font-weight: 600; margin-bottom: 2px; }
.node-type { font-size: 0.7rem; color: #9ca3af; text-transform: capitalize; }
.node-skill { font-size: 0.75rem; color: #6b7280; margin-top: 4px; }
.node-level { font-size: 0.7rem; color: #3b82f6; margin-top: 2px; }

/* 节点详情 */
.node-detail-panel {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.detail-header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.detail-header h4 { margin: 0; font-size: 1.15rem; }
.detail-badge { background: #f0f0ff; color: #667eea; font-size: 0.7rem; padding: 2px 8px; border-radius: 10px; text-transform: capitalize; }
.detail-desc { font-size: 0.85rem; color: #6b7280; margin: 8px 0 12px; line-height: 1.5; }
.detail-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.detail-item { text-align: center; }
.detail-label { display: block; font-size: 0.75rem; color: #9ca3af; margin-bottom: 2px; }
.detail-value { font-size: 0.95rem; font-weight: 500; }

/* NPC 对话 */
.npc-section, .quest-section { margin-top: 14px; border-top: 1px solid #f0f0f0; padding-top: 12px; }
.npc-section h5, .quest-section h5 { margin: 0 0 8px; font-size: 0.9rem; color: #333; }
.npc-list { display: flex; flex-direction: column; gap: 6px; }
.npc-item { display: flex; gap: 8px; align-items: flex-start; padding: 6px 10px; background: #faf5ff; border-radius: 8px; }
.npc-name { font-size: 0.8rem; font-weight: 600; color: #7c3aed; white-space: nowrap; }
.npc-dialog { font-size: 0.82rem; color: #555; line-height: 1.4; }

/* 任务池 */
.quest-list { list-style: none; padding: 0; margin: 0; }
.quest-list li { padding: 5px 10px; margin-bottom: 4px; background: #f0fff4; border-radius: 6px; font-size: 0.82rem; color: #2d6a4f; }
.quest-list li::before { content: '📝 '; }

.enter-btn {
  margin-top: 16px;
  width: 100%;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: white;
  border: none;
  border-radius: 10px;
  padding: 10px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}
.enter-btn:hover { opacity: 0.9; }

.loading { text-align: center; padding: 60px; color: #888; }
</style>
