<template>
  <div class="space-y-6">
    <div class="bg-white/95 rounded-2xl shadow-sm border border-slate-200 p-6">
      <div class="flex items-start justify-between gap-4 mb-4">
        <h3 class="text-lg font-semibold text-slate-900">核心规则</h3>
        <button
          v-if="editable"
          type="button"
          class="text-gray-400 hover:text-indigo-600 transition-colors"
          @click="emitEdit('world_setting.core_rules', '核心规则', worldSetting.core_rules)">
          <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
            <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
      <p class="text-slate-600 leading-7 whitespace-pre-line">{{ worldSetting.core_rules || '暂无' }}</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- 关键地点 -->
      <div class="bg-white/95 rounded-2xl shadow-sm border border-slate-200 p-6">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center text-slate-900 font-semibold">
            <svg class="mr-2 text-indigo-500" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18"/><path d="M6 18H4a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h2v7Z"/><path d="M18 18h2a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2h-2v7Z"/></svg>
            <span>关键地点</span>
          </div>
          <button
            v-if="editable"
            type="button"
            class="flex items-center gap-1 px-2 py-1 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors"
            @click="openAddLocation">
            <svg class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
            </svg>
            新增
          </button>
        </div>
        <ul class="space-y-4 text-sm text-slate-600">
          <li v-for="(item, index) in locations" :key="index" class="bg-slate-50 border border-slate-100 rounded-xl p-4 group relative">
            <div v-if="editable" class="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                type="button"
                class="p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
                title="编辑"
                @click="openEditLocation(index)">
                <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                </svg>
              </button>
              <button
                type="button"
                class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                title="删除"
                @click="confirmDeleteLocation(index)">
                <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9z" clip-rule="evenodd" />
                </svg>
              </button>
            </div>
            <strong class="block text-slate-800 mb-1">{{ item.title }}</strong>
            <span class="text-xs text-slate-500 leading-5">{{ item.description }}</span>
          </li>
          <li v-if="!locations.length" class="text-slate-400 text-sm">暂无数据</li>
        </ul>
      </div>

      <!-- 主要阵营 -->
      <div class="bg-white/95 rounded-2xl shadow-sm border border-slate-200 p-6">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center text-slate-900 font-semibold">
            <svg class="mr-2 text-indigo-500" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            <span>主要阵营</span>
          </div>
          <button
            v-if="editable"
            type="button"
            class="flex items-center gap-1 px-2 py-1 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors"
            @click="openAddFaction">
            <svg class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
            </svg>
            新增
          </button>
        </div>
        <ul class="space-y-4 text-sm text-slate-600">
          <li v-for="(item, index) in factions" :key="index" class="bg-slate-50 border border-slate-100 rounded-xl p-4 group relative">
            <div v-if="editable" class="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                type="button"
                class="p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
                title="编辑"
                @click="openEditFaction(index)">
                <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                </svg>
              </button>
              <button
                type="button"
                class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                title="删除"
                @click="confirmDeleteFaction(index)">
                <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9z" clip-rule="evenodd" />
                </svg>
              </button>
            </div>
            <strong class="block text-slate-800 mb-1">{{ item.title }}</strong>
            <span class="text-xs text-slate-500 leading-5">{{ item.description }}</span>
          </li>
          <li v-if="!factions.length" class="text-slate-400 text-sm">暂无数据</li>
        </ul>
      </div>
    </div>

    <!-- 单项编辑弹窗 -->
    <SingleWorldItemModal
      :show="showModal"
      :item="editingItem"
      :is-new="isNewItem"
      :item-label="currentItemLabel"
      @close="closeModal"
      @save="handleSave"
    />

    <!-- 删除确认弹窗 -->
    <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="showDeleteConfirm = false">
      <div class="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">确认删除</h3>
        <p class="text-gray-600 mb-6">确定要删除「{{ deletingItemName }}」吗？此操作无法撤销。</p>
        <div class="flex justify-end gap-3">
          <button
            @click="showDeleteConfirm = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-100 transition"
          >
            取消
          </button>
          <button
            @click="executeDelete"
            class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, defineEmits, defineProps } from 'vue'
import SingleWorldItemModal from '@/components/SingleWorldItemModal.vue'

interface ListItem {
  title: string
  description: string
}

interface WorldItem {
  name?: string
  description?: string
}

const props = defineProps<{
  data: Record<string, any> | null
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
  (e: 'update-world-setting', payload: { field: string; value: any[] }): void
}>()

const worldSetting = computed(() => props.data?.world_setting || {})

const normalizeList = (source: any): ListItem[] => {
  if (!source) return []
  if (Array.isArray(source)) {
    return source.map((item: any) => {
      if (typeof item === 'string') {
        const [title, ...rest] = item.split('：')
        return {
          title: title || item,
          description: rest.join('：') || '暂无描述'
        }
      }
      return {
        title: item?.name || '未命名',
        description: item?.description || item?.details || '暂无描述'
      }
    })
  }
  return []
}

const locations = computed(() => normalizeList(worldSetting.value?.key_locations))
const factions = computed(() => normalizeList(worldSetting.value?.factions))

// 获取原始数组
const getRawLocations = () => worldSetting.value?.key_locations || []
const getRawFactions = () => worldSetting.value?.factions || []

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}

// Modal 状态
const showModal = ref(false)
const editingItem = ref<WorldItem | null>(null)
const editingIndex = ref<number>(-1)
const isNewItem = ref(false)
const currentType = ref<'location' | 'faction'>('location')
const currentItemLabel = computed(() => currentType.value === 'location' ? '地点' : '阵营')

// 删除确认状态
const showDeleteConfirm = ref(false)
const deletingIndex = ref<number>(-1)
const deletingType = ref<'location' | 'faction'>('location')
const deletingItemName = computed(() => {
  const list = deletingType.value === 'location' ? locations.value : factions.value
  if (deletingIndex.value >= 0 && deletingIndex.value < list.length) {
    return list[deletingIndex.value]?.title || '未命名'
  }
  return ''
})

// 地点操作
const openAddLocation = () => {
  currentType.value = 'location'
  editingItem.value = null
  editingIndex.value = -1
  isNewItem.value = true
  showModal.value = true
}

const openEditLocation = (index: number) => {
  currentType.value = 'location'
  const raw = getRawLocations()[index]
  editingItem.value = { name: raw?.name || locations.value[index]?.title, description: raw?.description || locations.value[index]?.description }
  editingIndex.value = index
  isNewItem.value = false
  showModal.value = true
}

const confirmDeleteLocation = (index: number) => {
  deletingType.value = 'location'
  deletingIndex.value = index
  showDeleteConfirm.value = true
}

// 阵营操作
const openAddFaction = () => {
  currentType.value = 'faction'
  editingItem.value = null
  editingIndex.value = -1
  isNewItem.value = true
  showModal.value = true
}

const openEditFaction = (index: number) => {
  currentType.value = 'faction'
  const raw = getRawFactions()[index]
  editingItem.value = { name: raw?.name || factions.value[index]?.title, description: raw?.description || factions.value[index]?.description }
  editingIndex.value = index
  isNewItem.value = false
  showModal.value = true
}

const confirmDeleteFaction = (index: number) => {
  deletingType.value = 'faction'
  deletingIndex.value = index
  showDeleteConfirm.value = true
}

const closeModal = () => {
  showModal.value = false
  editingItem.value = null
  editingIndex.value = -1
}

const handleSave = (item: WorldItem) => {
  const field = currentType.value === 'location' ? 'key_locations' : 'factions'
  const rawList = currentType.value === 'location' ? [...getRawLocations()] : [...getRawFactions()]

  if (isNewItem.value) {
    rawList.push(item)
  } else if (editingIndex.value >= 0) {
    rawList[editingIndex.value] = item
  }

  emit('update-world-setting', { field, value: rawList })
  closeModal()
}

const executeDelete = () => {
  const field = deletingType.value === 'location' ? 'key_locations' : 'factions'
  const rawList = deletingType.value === 'location' ? [...getRawLocations()] : [...getRawFactions()]

  if (deletingIndex.value >= 0) {
    rawList.splice(deletingIndex.value, 1)
    emit('update-world-setting', { field, value: rawList })
  }

  showDeleteConfirm.value = false
  deletingIndex.value = -1
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'WorldSettingSection'
})
</script>
