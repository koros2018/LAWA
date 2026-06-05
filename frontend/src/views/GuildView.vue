<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/api'

interface Guild {
  id: string
  name: string
  emblem: string
  description: string
  level: number
  member_count: number
  member_limit: number
  xp: number
  buffs: Record<string, number>
}

interface GuildMember {
  user_id: string
  role: string
  contribution: number
  joined_at: string
}

interface GuildDetail {
  guild: Guild
  members: GuildMember[]
  my_role: string | null
}

interface GuildTask {
  id: string
  name: string
  description: string
  target_value: number
  current_value: number
  progress_pct: number
  xp_reward: number
  coin_reward: number
}

const userId = ref('')
const myGuild = ref<GuildDetail | null>(null)
const guildList = ref<Guild[]>([])
const selectedGuild = ref<GuildDetail | null>(null)
const guildTasks = ref<GuildTask[]>([])
const loading = ref(true)
const showCreate = ref(false)
const newGuild = ref({ name: '', language: 'en', description: '', emblem: '🛡️' })
const message = ref('')

onMounted(async () => {
  try {
    const u = JSON.parse(localStorage.getItem('lawa_user') || '{}')
    userId.value = u.id || ''

    // Load my guild & list
    const [myRes, listRes] = await Promise.allSettled([
      api.get(`/rpg/guild/my?user_id=${userId.value}`),
      api.get('/rpg/guilds'),
    ])

    if (myRes.status === 'fulfilled' && myRes.value.data?.guild) {
      myGuild.value = myRes.value.data
      // Load tasks
      try {
        const tRes = await api.get(`/rpg/guild/${myGuild.value!.guild.id}/tasks`)
        guildTasks.value = tRes.data.tasks || []
      } catch {}
    } else if (myRes.status === 'fulfilled') {
      myGuild.value = null
    }

    if (listRes.status === 'fulfilled') {
      guildList.value = listRes.value.data.guilds || []
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

async function viewGuild(guildId: string) {
  try {
    const res = await api.get(`/rpg/guild/${guildId}`)
    selectedGuild.value = res.data
  } catch (e) {
    console.error(e)
  }
}

async function createGuild() {
  try {
    message.value = ''
    await api.post('/rpg/guild/create', { ...newGuild.value, user_id: userId.value })
    showCreate.value = false
    location.reload()
  } catch (e: any) {
    message.value = e.response?.data?.detail || '创建失败'
  }
}

async function joinGuild(guildId: string) {
  try {
    await api.post('/rpg/guild/join', { user_id: userId.value, guild_id: guildId })
    location.reload()
  } catch (e: any) {
    message.value = e.response?.data?.detail || '加入失败'
  }
}

async function contribute() {
  try {
    await api.post('/rpg/guild/contribute', { user_id: userId.value, amount: 10, source: 'study' })
    location.reload()
  } catch {}
}

async function leaveGuild(guildId: string) {
  try {
    await api.post(`/rpg/guild/leave?user_id=${userId.value}&guild_id=${guildId}`)
    location.reload()
  } catch {}
}

const roleLabel = (role: string) => {
  return { owner: '👑 会长', co_owner: '⭐ 副会长', member: '👤 成员' }[role] || role
}
</script>

<template>
  <div class="guild-page" v-if="!loading">
    <h2>🏛️ LAWA 公会</h2>

    <!-- 我的公会 -->
    <div v-if="myGuild" class="my-guild-card">
      <div class="guild-banner">
        <span class="guild-emblem">{{ myGuild.guild.emblem }}</span>
        <div>
          <h3>{{ myGuild.guild.name }}</h3>
          <span class="guild-level">Lv.{{ myGuild.guild.level }}</span>
          <span class="guild-role">{{ roleLabel(myGuild.my_role || 'member') }}</span>
        </div>
      </div>
      <div class="guild-stats">
        <div class="gstat">
          <span class="gstat-val">{{ myGuild.guild.member_count }}/{{ myGuild.guild.member_limit }}</span>
          <span class="gstat-label">成员</span>
        </div>
        <div class="gstat">
          <span class="gstat-val">{{ myGuild.guild.xp || 0 }}</span>
          <span class="gstat-label">公会XP</span>
        </div>
        <div v-if="myGuild.guild.buffs?.xp_bonus_pct" class="gstat">
          <span class="gstat-val buff">+{{ myGuild.guild.buffs.xp_bonus_pct }}%</span>
          <span class="gstat-label">XP加成</span>
        </div>
      </div>

      <!-- 成员列表 -->
      <div class="members-section">
        <h4>👥 成员 ({{ myGuild.members.length }})</h4>
        <div class="member-row" v-for="m in myGuild.members" :key="m.user_id">
          <span>{{ roleLabel(m.role) }}</span>
          <span class="member-id">{{ m.user_id.slice(0, 8) }}...</span>
          <span class="member-contrib">⭐ {{ m.contribution || 0 }}</span>
        </div>
      </div>

      <!-- 公会任务 -->
      <div v-if="guildTasks.length" class="tasks-section">
        <h4>📋 公会任务</h4>
        <div class="task-row" v-for="t in guildTasks" :key="t.id">
          <span class="task-name">{{ t.name }}</span>
          <div class="task-bar-bg">
            <div class="task-bar-fill" :style="{ width: t.progress_pct + '%' }"></div>
          </div>
          <span class="task-pct">{{ t.progress_pct }}%</span>
        </div>
      </div>

      <div class="guild-actions">
        <button class="btn-primary" @click="contribute">⭐ 贡献 (+10)</button>
        <button class="btn-danger" @click="leaveGuild(myGuild.guild.id)">退出公会</button>
      </div>
    </div>

    <!-- 未加入公会 -->
    <div v-else class="no-guild">
      <p>你还没有加入公会</p>
      <button class="btn-primary" @click="showCreate = !showCreate">
        {{ showCreate ? '取消' : '🏛️ 创建公会' }}
      </button>

      <!-- 创建表单 -->
      <div v-if="showCreate" class="create-form">
        <input v-model="newGuild.name" placeholder="公会名称" class="input" />
        <select v-model="newGuild.language" class="input">
          <option value="en">English</option>
          <option value="zh">中文</option>
        </select>
        <input v-model="newGuild.description" placeholder="简介（选填）" class="input" />
        <button class="btn-primary" @click="createGuild">创建</button>
        <p v-if="message" class="error">{{ message }}</p>
      </div>
    </div>

    <!-- 公会大厅 -->
    <div class="guild-hall">
      <h3>🏛️ 公会大厅</h3>
      <p v-if="message" class="error">{{ message }}</p>
      <div class="guild-card" v-for="g in guildList" :key="g.id" @click="viewGuild(g.id)">
        <span class="emblem">{{ g.emblem }}</span>
        <div class="guild-info">
          <span class="gname">{{ g.name }}</span>
          <span class="gmeta">Lv.{{ g.level }} · {{ g.member_count }}/{{ g.member_limit }}人</span>
        </div>
        <button v-if="!myGuild" class="btn-sm" @click.stop="joinGuild(g.id)">加入</button>
      </div>
    </div>

    <!-- 选中公会详情 -->
    <div v-if="selectedGuild" class="guild-detail-panel">
      <h4>{{ selectedGuild.guild.emblem }} {{ selectedGuild.guild.name }}</h4>
      <p>{{ selectedGuild.guild.description }}</p>
      <p>Lv.{{ selectedGuild.guild.level }} · {{ selectedGuild.guild.member_count }}成员 · {{ selectedGuild.guild.xp }}XP</p>
      <div v-if="selectedGuild.guild.buffs?.xp_bonus_pct">
        🎁 XP加成: +{{ selectedGuild.guild.buffs.xp_bonus_pct }}%
      </div>
    </div>
  </div>
  <div v-else class="loading">加载中...</div>
</template>

<style scoped>
.guild-page { padding: 16px; max-width: 800px; margin: 0 auto; }

/* 我的公会卡片 */
.my-guild-card {
  background: linear-gradient(135deg, #1e1b4b, #312e81);
  color: #e0e7ff;
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 20px;
}
.guild-banner { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.guild-emblem { font-size: 2.5rem; }
.guild-banner h3 { margin: 0; font-size: 1.2rem; }
.guild-level {
  background: #f59e0b; color: #000; font-size: 0.75rem;
  padding: 2px 8px; border-radius: 10px; margin-right: 8px;
}
.guild-role { font-size: 0.8rem; color: #c084fc; }
.guild-stats { display: flex; gap: 16px; margin-bottom: 16px; }
.gstat { text-align: center; }
.gstat-val { font-size: 1.1rem; font-weight: 700; display: block; }
.gstat-val.buff { color: #34d399; }
.gstat-label { font-size: 0.7rem; color: #94a3b8; }

.members-section, .tasks-section { margin-bottom: 16px; }
.members-section h4, .tasks-section h4 { margin: 0 0 8px; font-size: 0.9rem; }
.member-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 0.85rem; }
.member-id { flex: 1; color: #94a3b8; font-size: 0.75rem; }
.member-contrib { color: #f59e0b; }

.task-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 0.8rem; }
.task-name { width: 160px; }
.task-bar-bg { flex: 1; height: 6px; background: rgba(255,255,255,0.2); border-radius: 3px; overflow: hidden; }
.task-bar-fill { height: 100%; background: #34d399; border-radius: 3px; transition: width 0.3s; }
.task-pct { color: #94a3b8; min-width: 40px; text-align: right; }

.guild-actions { display: flex; gap: 10px; }
.btn-primary {
  background: #6366f1; color: white; border: none; padding: 8px 16px;
  border-radius: 8px; cursor: pointer; font-size: 0.85rem;
}
.btn-danger {
  background: transparent; color: #f87171; border: 1px solid #f87171;
  padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 0.85rem;
}
.btn-sm {
  background: #6366f1; color: white; border: none; padding: 4px 12px;
  border-radius: 6px; cursor: pointer; font-size: 0.8rem;
}

/* 未加入 */
.no-guild { text-align: center; padding: 40px; background: white; border-radius: 12px; margin-bottom: 20px; }
.create-form { display: flex; flex-direction: column; gap: 8px; max-width: 300px; margin: 16px auto 0; }
.input { padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.9rem; }

/* 大厅 */
.guild-hall { background: white; border-radius: 12px; padding: 16px; margin-bottom: 20px; }
.guild-hall h3 { margin: 0 0 12px; }
.guild-card { display: flex; align-items: center; gap: 12px; padding: 12px; border-radius: 10px; cursor: pointer; transition: background 0.2s; }
.guild-card:hover { background: #f3f4f6; }
.emblem { font-size: 1.8rem; }
.guild-info { flex: 1; }
.gname { display: block; font-weight: 600; }
.gmeta { font-size: 0.75rem; color: #6b7280; }

.guild-detail-panel {
  background: white; border-radius: 12px; padding: 20px; margin-top: 16px;
}
.guild-detail-panel h4 { margin: 0 0 8px; }
.error { color: #ef4444; font-size: 0.85rem; margin-top: 8px; }
.loading { text-align: center; padding: 60px; color: #888; }
</style>
