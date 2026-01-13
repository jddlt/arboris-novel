<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">伏笔系统</h2>
        <p class="text-sm text-slate-500">追踪伏笔的埋设与回收，防止断线</p>
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
          新增伏笔
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div v-if="threads.length" class="grid grid-cols-3 gap-4">
      <div class="bg-indigo-50 rounded-xl p-4">
        <div class="text-2xl font-bold text-indigo-600">{{ activeThreads.length }}</div>
        <div class="text-sm text-indigo-600/70">活跃伏笔</div>
      </div>
      <div class="bg-green-50 rounded-xl p-4">
        <div class="text-2xl font-bold text-green-600">{{ revealedThreads.length }}</div>
        <div class="text-sm text-green-600/70">已揭示</div>
      </div>
      <div class="bg-amber-50 rounded-xl p-4">
        <div class="text-2xl font-bold text-amber-600">{{ overdueThreads.length }}</div>
        <div class="text-sm text-amber-600/70">待回收</div>
      </div>
    </div>

    <!-- 活跃伏笔 -->
    <div v-if="activeThreads.length" class="space-y-4">
      <h3 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-indigo-500"></span>
        活跃伏笔
      </h3>
      <div class="space-y-3">
        <div
          v-for="(thread, index) in activeThreads"
          :key="thread.id"
          class="bg-white/95 rounded-xl border border-slate-200 shadow-sm p-5 group relative"
        >
          <!-- 操作按钮 -->
          <div v-if="editable" class="absolute top-4 right-4 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              type="button"
              class="p-1.5 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded transition-colors"
              title="标记已揭示"
              @click="markRevealed(thread)"
            >
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
            </button>
            <button
              type="button"
              class="p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
              title="编辑"
              @click="openEditModal(findThreadIndex(thread))"
            >
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
              </svg>
            </button>
            <button
              type="button"
              class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
              title="删除"
              @click="confirmDelete(findThreadIndex(thread))"
            >
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>

          <div class="pr-24">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-lg">🔮</span>
              <h4 class="font-semibold text-slate-900">{{ thread.title }}</h4>
              <span
                v-if="isOverdue(thread)"
                class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full"
              >
                待回收
              </span>
            </div>
            <p class="text-sm text-slate-500 mb-2">
              第{{ thread.plant_chapter }}章埋设 → 预计第{{ thread.reveal_chapter }}章揭示
            </p>
            <p v-if="thread.description" class="text-sm text-slate-600 mb-3">{{ thread.description }}</p>

            <!-- 线索 -->
            <div v-if="thread.clues && thread.clues.length" class="flex flex-wrap gap-2">
              <span
                v-for="(clue, ci) in thread.clues.slice(0, 5)"
                :key="ci"
                class="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded"
              >
                第{{ clue.chapter }}章：{{ clue.content.length > 20 ? clue.content.slice(0, 20) + '...' : clue.content }}
              </span>
              <span v-if="thread.clues.length > 5" class="text-xs text-slate-400">
                +{{ thread.clues.length - 5 }} 条线索
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 已揭示伏笔 -->
    <div v-if="revealedThreads.length" class="space-y-4">
      <h3 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-green-500"></span>
        已揭示
      </h3>
      <div class="space-y-2">
        <div
          v-for="thread in revealedThreads"
          :key="thread.id"
          class="bg-green-50/50 rounded-lg border border-green-100 p-4 group relative"
        >
          <div v-if="editable" class="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              type="button"
              class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
              title="删除"
              @click="confirmDelete(findThreadIndex(thread))"
            >
              <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-green-600">✅</span>
            <span class="font-medium text-slate-800">{{ thread.title }}</span>
            <span class="text-xs text-slate-500">
              第{{ thread.actual_reveal_chapter || thread.reveal_chapter }}章揭示
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!threads.length" class="bg-slate-50 rounded-2xl border border-dashed border-slate-300 p-12 text-center">
      <svg class="mx-auto h-12 w-12 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
      <p class="mt-4 text-sm text-slate-500">暂无伏笔，点击「新增伏笔」开始追踪</p>
    </div>

    <!-- 编辑弹窗 -->
    <SingleForeshadowingModal
      :show="showModal"
      :thread="editingThread"
      :is-new="isNewThread"
      @close="closeModal"
      @save="handleSave"
    />

    <!-- 揭示确认弹窗 -->
    <div v-if="showRevealConfirm" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="showRevealConfirm = false">
      <div class="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">标记伏笔已揭示</h3>
        <p class="text-gray-600 mb-4">请输入实际揭示的章节号：</p>
        <input
          type="number"
          v-model.number="revealChapter"
          min="1"
          class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition mb-4"
          placeholder="章节号"
        />
        <div class="flex justify-end gap-3">
          <button
            @click="showRevealConfirm = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-100 transition"
          >
            取消
          </button>
          <button
            @click="executeReveal"
            :disabled="!revealChapter || revealChapter < 1"
            class="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition disabled:opacity-50"
          >
            确认揭示
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="showDeleteConfirm = false">
      <div class="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">确认删除</h3>
        <p class="text-gray-600 mb-6">确定要删除伏笔「{{ deletingThreadTitle }}」吗？</p>
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
import SingleForeshadowingModal from '@/components/SingleForeshadowingModal.vue'

interface Clue {
  chapter: number
  content: string
}

interface ForeshadowingThread {
  id?: string
  title?: string
  description?: string
  plant_chapter?: number
  reveal_chapter?: number
  actual_reveal_chapter?: number | null
  clues?: Clue[]
  status?: string
}

const props = defineProps<{
  data: Record<string, any> | null
  editable?: boolean
  currentChapter?: number
}>()

const emit = defineEmits<{
  (e: 'update-foreshadowing', threads: ForeshadowingThread[]): void
}>()

const foreshadowingData = computed(() => props.data?.foreshadowing || {})
const threads = computed<ForeshadowingThread[]>(() => foreshadowingData.value?.threads || [])

const activeThreads = computed(() => threads.value.filter(t => t.status === 'active'))
const revealedThreads = computed(() => threads.value.filter(t => t.status === 'revealed'))
const overdueThreads = computed(() => {
  const current = props.currentChapter || 0
  return activeThreads.value.filter(t => (t.reveal_chapter || 0) <= current)
})

const isOverdue = (thread: ForeshadowingThread) => {
  const current = props.currentChapter || 0
  return thread.status === 'active' && (thread.reveal_chapter || 0) <= current
}

const findThreadIndex = (thread: ForeshadowingThread) => {
  return threads.value.findIndex(t => t.id === thread.id || t.title === thread.title)
}

// Modal 状态
const showModal = ref(false)
const editingThread = ref<ForeshadowingThread | null>(null)
const editingIndex = ref<number>(-1)
const isNewThread = ref(false)

// 揭示确认状态
const showRevealConfirm = ref(false)
const revealingThread = ref<ForeshadowingThread | null>(null)
const revealChapter = ref<number | undefined>()

// 删除确认状态
const showDeleteConfirm = ref(false)
const deletingIndex = ref<number>(-1)
const deletingThreadTitle = computed(() => {
  if (deletingIndex.value >= 0 && deletingIndex.value < threads.value.length) {
    return threads.value[deletingIndex.value]?.title || '未命名'
  }
  return ''
})

const openAddModal = () => {
  editingThread.value = null
  editingIndex.value = -1
  isNewThread.value = true
  showModal.value = true
}

const openEditModal = (index: number) => {
  editingThread.value = threads.value[index]
  editingIndex.value = index
  isNewThread.value = false
  showModal.value = true
}

const closeModal = () => {
  showModal.value = false
  editingThread.value = null
  editingIndex.value = -1
}

const handleSave = (thread: ForeshadowingThread) => {
  const newThreads = [...threads.value]

  if (isNewThread.value) {
    if (!thread.id) {
      thread.id = crypto.randomUUID()
    }
    if (!thread.status) {
      thread.status = 'active'
    }
    newThreads.push(thread)
  } else if (editingIndex.value >= 0) {
    newThreads[editingIndex.value] = thread
  }

  emit('update-foreshadowing', newThreads)
  closeModal()
}

const markRevealed = (thread: ForeshadowingThread) => {
  revealingThread.value = thread
  revealChapter.value = thread.reveal_chapter
  showRevealConfirm.value = true
}

const executeReveal = () => {
  if (!revealingThread.value || !revealChapter.value) return

  const index = findThreadIndex(revealingThread.value)
  if (index >= 0) {
    const newThreads = [...threads.value]
    newThreads[index] = {
      ...newThreads[index],
      status: 'revealed',
      actual_reveal_chapter: revealChapter.value,
    }
    emit('update-foreshadowing', newThreads)
  }

  showRevealConfirm.value = false
  revealingThread.value = null
  revealChapter.value = undefined
}

const confirmDelete = (index: number) => {
  deletingIndex.value = index
  showDeleteConfirm.value = true
}

const executeDelete = () => {
  if (deletingIndex.value >= 0) {
    const newThreads = threads.value.filter((_, i) => i !== deletingIndex.value)
    emit('update-foreshadowing', newThreads)
  }
  showDeleteConfirm.value = false
  deletingIndex.value = -1
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ForeshadowingSection'
})
</script>
