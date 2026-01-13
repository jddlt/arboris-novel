<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">卷结构</h2>
        <p class="text-sm text-slate-500">管理长篇小说的卷/篇章划分</p>
      </div>
      <div v-if="editable" class="flex items-center gap-2">
        <button
          type="button"
          class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg"
          @click="openAddModal"
        >
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
          </svg>
          新增卷
        </button>
      </div>
    </div>

    <div v-if="volumes.length" class="space-y-4">
      <div
        v-for="(volume, index) in volumes"
        :key="volume.id || index"
        class="bg-white/95 rounded-2xl border border-slate-200 shadow-sm p-6 group relative"
      >
        <!-- 操作按钮 -->
        <div v-if="editable" class="absolute top-4 right-4 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            type="button"
            class="p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
            title="编辑卷"
            @click="openEditModal(index)"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
              <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
            </svg>
          </button>
          <button
            type="button"
            class="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            title="删除卷"
            @click="confirmDelete(index)"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>

        <div class="flex items-start gap-4">
          <!-- 卷号标识 -->
          <div class="flex-shrink-0 w-14 h-14 rounded-xl flex items-center justify-center text-white font-bold text-lg"
            :class="{
              'bg-green-500': volume.status === 'completed',
              'bg-indigo-500': volume.status === 'in_progress',
              'bg-slate-400': volume.status === 'planned'
            }"
          >
            {{ volume.volume_number }}
          </div>

          <!-- 卷信息 -->
          <div class="flex-1 min-w-0 pr-16">
            <div class="flex items-center gap-2 mb-1">
              <h3 class="text-lg font-semibold text-slate-900 truncate">{{ volume.title }}</h3>
              <span
                class="text-xs px-2 py-0.5 rounded-full"
                :class="{
                  'bg-green-100 text-green-700': volume.status === 'completed',
                  'bg-indigo-100 text-indigo-700': volume.status === 'in_progress',
                  'bg-slate-100 text-slate-600': volume.status === 'planned'
                }"
              >
                {{ statusLabel(volume.status) }}
              </span>
            </div>
            <p class="text-sm text-slate-500 mb-2">
              第{{ volume.chapter_start }}章 ~ 第{{ volume.chapter_end }}章
              <span class="text-slate-400">（共{{ (volume.chapter_end || 0) - (volume.chapter_start || 0) + 1 }}章）</span>
            </p>
            <p v-if="volume.summary" class="text-sm text-slate-600 line-clamp-2">{{ volume.summary }}</p>
            <div v-if="volume.core_conflict || volume.climax" class="mt-2 flex flex-wrap gap-2">
              <span v-if="volume.core_conflict" class="text-xs bg-amber-50 text-amber-700 px-2 py-1 rounded">
                冲突：{{ volume.core_conflict }}
              </span>
              <span v-if="volume.climax" class="text-xs bg-rose-50 text-rose-700 px-2 py-1 rounded">
                高潮：{{ volume.climax }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="bg-slate-50 rounded-2xl border border-dashed border-slate-300 p-12 text-center">
      <svg class="mx-auto h-12 w-12 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
      <p class="mt-4 text-sm text-slate-500">暂无卷结构，点击「新增卷」开始规划</p>
    </div>

    <!-- 编辑弹窗 -->
    <SingleVolumeModal
      :show="showModal"
      :volume="editingVolume"
      :is-new="isNewVolume"
      :next-volume-number="nextVolumeNumber"
      @close="closeModal"
      @save="handleSave"
    />

    <!-- 删除确认弹窗 -->
    <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="showDeleteConfirm = false">
      <div class="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">确认删除</h3>
        <p class="text-gray-600 mb-6">确定要删除「{{ deletingVolumeTitle }}」吗？此操作无法撤销。</p>
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
import SingleVolumeModal from '@/components/SingleVolumeModal.vue'

interface Volume {
  id?: string
  volume_number?: number
  title?: string
  chapter_start?: number
  chapter_end?: number
  summary?: string
  core_conflict?: string
  climax?: string
  status?: string
}

const props = defineProps<{
  data: Record<string, any> | null
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'update-volumes', volumes: Volume[]): void
}>()

const volumes = computed<Volume[]>(() => {
  const list = props.data?.volumes || []
  return [...list].sort((a, b) => (a.volume_number || 0) - (b.volume_number || 0))
})

const nextVolumeNumber = computed(() => {
  if (volumes.value.length === 0) return 1
  return Math.max(...volumes.value.map(v => v.volume_number || 0)) + 1
})

const statusLabel = (status?: string) => {
  const labels: Record<string, string> = {
    completed: '已完成',
    in_progress: '写作中',
    planned: '规划中',
  }
  return labels[status || 'planned'] || '规划中'
}

// Modal 状态
const showModal = ref(false)
const editingVolume = ref<Volume | null>(null)
const editingIndex = ref<number>(-1)
const isNewVolume = ref(false)

// 删除确认状态
const showDeleteConfirm = ref(false)
const deletingIndex = ref<number>(-1)
const deletingVolumeTitle = computed(() => {
  if (deletingIndex.value >= 0 && deletingIndex.value < volumes.value.length) {
    return volumes.value[deletingIndex.value]?.title || '未命名'
  }
  return ''
})

const openAddModal = () => {
  editingVolume.value = null
  editingIndex.value = -1
  isNewVolume.value = true
  showModal.value = true
}

const openEditModal = (index: number) => {
  editingVolume.value = volumes.value[index]
  editingIndex.value = index
  isNewVolume.value = false
  showModal.value = true
}

const closeModal = () => {
  showModal.value = false
  editingVolume.value = null
  editingIndex.value = -1
}

const handleSave = (volume: Volume) => {
  const newVolumes = [...volumes.value]

  if (isNewVolume.value) {
    newVolumes.push(volume)
    newVolumes.sort((a, b) => (a.volume_number || 0) - (b.volume_number || 0))
  } else if (editingIndex.value >= 0) {
    newVolumes[editingIndex.value] = volume
  }

  emit('update-volumes', newVolumes)
  closeModal()
}

const confirmDelete = (index: number) => {
  deletingIndex.value = index
  showDeleteConfirm.value = true
}

const executeDelete = () => {
  if (deletingIndex.value >= 0) {
    const newVolumes = volumes.value.filter((_, i) => i !== deletingIndex.value)
    emit('update-volumes', newVolumes)
  }
  showDeleteConfirm.value = false
  deletingIndex.value = -1
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'VolumeSection'
})
</script>
