<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'

interface ShopItem {
  id: string; code: string; type: string; name: string; emoji: string
  description: string; slot?: string; rarity: string; rarity_color: string
  price_coin: number; effects?: Record<string,number>
  effect_type?: string; effect_value?: number; effect_duration_min?: number
}
interface InvItem {
  inv_id: string; item_type: string; quantity: number; equipped: boolean
  info: { name: string; emoji: string; slot?: string; effects?: Record<string,number>; effect_type?: string }
}

const userId = ref('')
const shopItems = ref<ShopItem[]>([])
const inventory = ref<InvItem[]>([])
const equipped = ref<{ slots: Record<string,any>; active_buffs: Record<string,number> }>({ slots:{}, active_buffs:{} })
const tab = ref('shop')
const message = ref('')

onMounted(async () => {
  const u = JSON.parse(localStorage.getItem('lawa_user') || '{}')
  userId.value = u.id || ''
  await refresh()
})

async function refresh() {
  try {
    const [s, i, e] = await Promise.all([
      api.get('/rpg/shop'), api.get(`/rpg/inventory?user_id=${userId.value}`),
      api.get(`/rpg/inventory/equipped?user_id=${userId.value}`),
    ])
    shopItems.value = s.data.items; inventory.value = i.data.items; equipped.value = e.data
  } catch {}
}

async function buy(item: ShopItem) {
  try {
    await api.post('/rpg/shop/buy', { user_id: userId.value, item_type: item.type, item_id: item.id, quantity: 1 })
    await refresh()
  } catch (e: any) { message.value = e.response?.data?.detail || '购买失败' }
}
async function equip(inv: InvItem) {
  try { await api.post('/rpg/inventory/equip', { user_id: userId.value, inv_id: inv.inv_id }); await refresh() }
  catch (e: any) { message.value = e.response?.data?.detail || '装备失败' }
}
async function useItem(inv: InvItem) {
  try { await api.post('/rpg/inventory/use', { user_id: userId.value, inv_id: inv.inv_id }); await refresh() }
  catch (e: any) { message.value = e.response?.data?.detail || '使用失败' }
}

const rarityLabel = (r: string) => ({ common:'普通', rare:'稀有', epic:'史诗', legendary:'传说' }[r] || r)
</script>

<template>
  <div class="shop-page">
    <h2>🎒 道具商店</h2>
    <div class="tabs">
      <button :class="{active:tab==='shop'}" @click="tab='shop'">🏪 商店</button>
      <button :class="{active:tab==='inventory'}" @click="tab='inventory'">🎒 背包</button>
      <button :class="{active:tab==='equipped'}" @click="tab='equipped'">⚔️ 已装备</button>
    </div>
    <p v-if="message" class="error">{{ message }}</p>

    <!-- 商店 -->
    <div v-if="tab==='shop'" class="grid">
      <div v-for="item in shopItems" :key="item.id" class="item-card">
        <div class="item-header">
          <span class="item-emoji">{{ item.emoji }}</span>
          <span class="item-name">{{ item.name }}</span>
          <span class="item-rarity" :style="{color:item.rarity_color}">{{ rarityLabel(item.rarity) }}</span>
        </div>
        <div class="item-desc">{{ item.description }}</div>
        <div v-if="item.type==='equipment'" class="item-meta">
          <span>{{ item.slot }}</span>
          <span v-for="(v,k) in item.effects" :key="k">+{{ v }}% {{ k }}</span>
        </div>
        <div v-if="item.type==='consumable'" class="item-meta">
          <span>{{ item.effect_type }} +{{ item.effect_value }}</span>
          <span v-if="item.effect_duration_min">{{ item.effect_duration_min }}min</span>
        </div>
        <button @click="buy(item)" class="btn-buy">{{ item.price_coin }}🪙 购买</button>
      </div>
    </div>

    <!-- 背包 -->
    <div v-if="tab==='inventory'">
      <div v-for="item in inventory" :key="item.inv_id" class="inv-row">
        <span class="inv-emoji">{{ item.info?.emoji }}</span>
        <span class="inv-name">{{ item.info?.name }}</span>
        <span class="inv-qty">x{{ item.quantity }}</span>
        <span v-if="item.equipped" class="equipped-badge">✅ 已装备</span>
        <template v-if="item.item_type==='equipment' && !item.equipped">
          <button @click="equip(item)" class="btn-sm">装备</button>
        </template>
        <template v-if="item.item_type==='consumable' && item.quantity > 0">
          <button @click="useItem(item)" class="btn-sm">使用</button>
        </template>
      </div>
    </div>

    <!-- 已装备 -->
    <div v-if="tab==='equipped'">
      <div class="buff-panel">
        <h4>🔮 当前 Buff</h4>
        <div class="buff-row" v-for="(v,k) in equipped.active_buffs" :key="k" v-show="v>0">
          <span>{{ k }}</span><span class="buff-val">+{{ v }}%</span>
        </div>
      </div>
      <div class="slots-grid">
        <div v-for="(eq, slot) in equipped.slots" :key="slot" class="slot-card">
          <span>{{ eq.emoji }}</span><span>{{ eq.name }}</span><span class="slot-name">{{ slot }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shop-page { padding: 16px; max-width: 800px; margin: 0 auto; }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tabs button { padding: 8px 16px; border: none; border-radius: 8px; cursor: pointer; background: #e5e7eb; }
.tabs button.active { background: #6366f1; color: white; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.item-card { background: white; border-radius: 12px; padding: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
.item-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.item-emoji { font-size: 1.5rem; } .item-name { font-weight: 600; font-size: 0.95rem; flex:1; }
.item-rarity { font-size: 0.7rem; } .item-desc { font-size: 0.8rem; color: #6b7280; margin-bottom: 8px; }
.item-meta { display: flex; gap: 8px; font-size: 0.75rem; color: #9ca3af; margin-bottom: 10px; }
.btn-buy { width: 100%; padding: 8px; background: #f59e0b; color: #000; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; }
.btn-sm { padding: 4px 12px; background: #6366f1; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.8rem; }
.inv-row { display: flex; align-items: center; gap: 10px; padding: 12px; background: white; border-radius: 10px; margin-bottom: 8px; }
.inv-emoji { font-size: 1.5rem; } .inv-name { flex:1; font-weight: 500; }
.inv-qty { color: #6b7280; } .equipped-badge { color: #22c55e; font-size: 0.8rem; }
.buff-panel { background: white; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.buff-row { display: flex; justify-content: space-between; padding: 4px 0; }
.buff-val { color: #22c55e; font-weight: 700; }
.slots-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.slot-card { background: white; border-radius: 10px; padding: 12px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.slot-name { font-size: 0.7rem; color: #9ca3af; }
.error { color: #ef4444; font-size: 0.85rem; }
</style>
