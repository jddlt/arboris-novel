<template>
  <div v-if="show" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
      <!-- 头部 -->
      <div class="flex items-center justify-between p-6 border-b border-gray-200 flex-shrink-0">
        <h3 class="text-lg font-semibold text-gray-900">开始创作</h3>
        <button
          @click="$emit('close')"
          class="text-gray-400 hover:text-gray-600 transition-colors"
        >
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </div>

      <!-- 内容 -->
      <div class="p-6 space-y-4 overflow-y-auto flex-1">
        <!-- 章节基本信息 -->
        <div class="bg-indigo-50 rounded-lg p-4">
          <div class="flex items-center gap-3 mb-2">
            <div class="w-8 h-8 bg-indigo-500 rounded-full flex items-center justify-center text-white font-bold text-sm">
              {{ chapterNumber }}
            </div>
            <div>
              <h4 class="font-semibold text-gray-900">第{{ chapterNumber }}章</h4>
              <p class="text-sm text-gray-600">{{ chapterTitle || '未命名章节' }}</p>
            </div>
          </div>
          <div v-if="chapterSummary" class="mt-3 text-sm text-gray-700 bg-white/50 rounded p-3">
            <span class="font-medium text-gray-800">章节概述：</span>
            {{ chapterSummary }}
          </div>
        </div>

        <!-- 上下文选择区域 -->
        <div v-if="hasContextOptions" class="space-y-4">
          <div class="flex items-center justify-between">
            <h4 class="font-medium text-gray-900">选择写作上下文</h4>
            <button
              v-if="hasRecommendedItems"
              @click="selectRecommended"
              class="text-xs text-indigo-600 hover:text-indigo-700"
            >
              选择推荐项
            </button>
          </div>

          <!-- 备忘录选择 -->
          <div v-if="contextOptions.notes.length > 0" class="border border-gray-200 rounded-lg overflow-hidden">
            <div class="bg-gray-50 px-4 py-2 border-b border-gray-200">
              <div class="flex items-center justify-between">
                <span class="text-sm font-medium text-gray-700">作者备忘录</span>
                <span class="text-xs text-gray-500">{{ selectedNoteIds.length }}/{{ contextOptions.notes.length }}</span>
              </div>
            </div>
            <div class="max-h-40 overflow-y-auto divide-y divide-gray-100">
              <label
                v-for="note in contextOptions.notes"
                :key="note.id"
                class="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  :checked="selectedNoteIds.includes(note.id)"
                  @change="toggleSelection('note', note.id)"
                  class="mt-0.5 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-medium text-gray-900 truncate">{{ note.title }}</span>
                    <span class="text-xs px-1.5 py-0.5 rounded-full" :class="getNoteTypeConfig(note.type).class">
                      {{ getNoteTypeConfig(note.type).label }}
                    </span>
                    <span v-if="note.is_recommended" class="text-xs text-amber-600 font-medium">推荐</span>
                  </div>
                  <p class="text-xs text-gray-500 line-clamp-1 mt-0.5">{{ note.content }}</p>
                </div>
              </label>
            </div>
          </div>

          <!-- 角色状态选择 -->
          <div v-if="contextOptions.states.length > 0" class="border border-gray-200 rounded-lg overflow-hidden">
            <div class="bg-gray-50 px-4 py-2 border-b border-gray-200">
              <div class="flex items-center justify-between">
                <span class="text-sm font-medium text-gray-700">角色状态</span>
                <span class="text-xs text-gray-500">{{ selectedStateIds.length }}/{{ contextOptions.states.length }}</span>
              </div>
            </div>
            <div class="max-h-40 overflow-y-auto divide-y divide-gray-100">
              <label
                v-for="state in contextOptions.states"
                :key="state.id"
                class="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  :checked="selectedStateIds.includes(state.id)"
                  @change="toggleSelection('state', state.id)"
                  class="mt-0.5 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-medium text-gray-900">{{ state.character_name }}</span>
                    <span class="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">
                      第{{ state.chapter_number }}章
                    </span>
                  </div>
                  <p class="text-xs text-gray-500 mt-0.5">{{ state.summary }}</p>
                </div>
              </label>
            </div>
          </div>
        </div>

        <!-- 加载上下文中 -->
        <div v-else-if="loadingContext" class="flex items-center justify-center py-6">
          <div class="flex items-center gap-2 text-gray-500">
            <svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span class="text-sm">正在加载上下文选项...</span>
          </div>
        </div>

        <!-- 写作要求输入 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            写作要求 <span class="text-gray-400 font-normal">(可选)</span>
          </label>
          <textarea
            v-model="writingNotes"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
            rows="3"
            placeholder="输入额外的写作要求，如风格偏好、情节重点、情绪基调等..."
          ></textarea>
          <p class="mt-1 text-xs text-gray-500">
            添加写作要求可以让生成的内容更符合您的预期
          </p>
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="flex items-center justify-between gap-3 p-6 border-t border-gray-200 flex-shrink-0">
        <div class="text-sm text-gray-500">
          <span v-if="selectedNoteIds.length || selectedStateIds.length">
            已选择 {{ selectedNoteIds.length }} 条备忘录，{{ selectedStateIds.length }} 个角色状态
          </span>
        </div>
        <div class="flex items-center gap-3">
          <button
            @click="$emit('close')"
            class="px-4 py-2 text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg transition-colors"
          >
            取消
          </button>
          <button
            @click="handleGenerate"
            class="px-6 py-2 bg-indigo-600 text-white hover:bg-indigo-700 rounded-lg transition-colors flex items-center gap-2"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
            </svg>
            开始生成
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onUnmounted } from 'vue'
import { getGenerationContextOptions, type GenerationContextOptions } from '@/api/authorNotes'

// ==================== 常量 ====================

const EMPTY_CONTEXT_OPTIONS: GenerationContextOptions = {
  notes: [],
  states: [],
  recommended_note_ids: [],
  recommended_state_ids: []
}

const NOTE_TYPE_CONFIG: Record<string, { class: string; label: string }> = {
  chapter: { class: 'bg-blue-100 text-blue-700', label: '章节' },
  character_secret: { class: 'bg-purple-100 text-purple-700', label: '秘密' },
  style: { class: 'bg-green-100 text-green-700', label: '风格' },
  todo: { class: 'bg-amber-100 text-amber-700', label: '待办' },
  global: { class: 'bg-gray-100 text-gray-700', label: '通用' }
}

const DEFAULT_NOTE_TYPE_CONFIG = { class: 'bg-gray-100 text-gray-700', label: '其他' }

// ==================== Props & Emits ====================

interface Props {
  show: boolean
  chapterNumber: number
  chapterTitle?: string
  chapterSummary?: string
  projectId: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
  generate: [{
    chapterNumber: number
    writingNotes?: string
    selectedNoteIds?: number[]
    selectedStateIds?: number[]
  }]
}>()

// ==================== 状态 ====================

const writingNotes = ref('')
const loadingContext = ref(false)
const contextOptions = ref<GenerationContextOptions>({ ...EMPTY_CONTEXT_OPTIONS })
const selectedNoteIds = ref<number[]>([])
const selectedStateIds = ref<number[]>([])

// 用于取消过期请求
let requestId = 0

// ==================== 计算属性 ====================

const hasContextOptions = computed(() => {
  return !loadingContext.value &&
    (contextOptions.value.notes.length > 0 || contextOptions.value.states.length > 0)
})

const hasRecommendedItems = computed(() => {
  return contextOptions.value.recommended_note_ids.length > 0 ||
         contextOptions.value.recommended_state_ids.length > 0
})

// ==================== 方法 ====================

function getNoteTypeConfig(type: string) {
  return NOTE_TYPE_CONFIG[type] || DEFAULT_NOTE_TYPE_CONFIG
}

async function loadContextOptions() {
  if (!props.projectId || !props.chapterNumber) return

  // 记录当前请求ID，用于忽略过期响应
  const currentRequestId = ++requestId
  loadingContext.value = true

  try {
    const options = await getGenerationContextOptions(props.projectId, props.chapterNumber)

    // 如果组件已关闭或有新请求，忽略此响应
    if (currentRequestId !== requestId) return

    contextOptions.value = options
    // 默认选中推荐项
    selectedNoteIds.value = [...options.recommended_note_ids]
    selectedStateIds.value = [...options.recommended_state_ids]
  } catch (e) {
    // 忽略过期请求的错误
    if (currentRequestId !== requestId) return

    console.error('加载上下文选项失败:', e)
    contextOptions.value = { ...EMPTY_CONTEXT_OPTIONS }
  } finally {
    if (currentRequestId === requestId) {
      loadingContext.value = false
    }
  }
}

function toggleSelection(type: 'note' | 'state', id: number) {
  const targetArray = type === 'note' ? selectedNoteIds : selectedStateIds
  if (targetArray.value.includes(id)) {
    targetArray.value = targetArray.value.filter(item => item !== id)
  } else {
    targetArray.value = [...targetArray.value, id]
  }
}

function selectRecommended() {
  selectedNoteIds.value = [...contextOptions.value.recommended_note_ids]
  selectedStateIds.value = [...contextOptions.value.recommended_state_ids]
}

function resetState() {
  writingNotes.value = ''
  selectedNoteIds.value = []
  selectedStateIds.value = []
  contextOptions.value = { ...EMPTY_CONTEXT_OPTIONS }
  loadingContext.value = false
}

function handleGenerate() {
  emit('generate', {
    chapterNumber: props.chapterNumber,
    writingNotes: writingNotes.value.trim() || undefined,
    selectedNoteIds: selectedNoteIds.value.length > 0 ? [...selectedNoteIds.value] : undefined,
    selectedStateIds: selectedStateIds.value.length > 0 ? [...selectedStateIds.value] : undefined
  })
}

// ==================== 生命周期 ====================

watch(() => props.show, (newVal) => {
  if (newVal) {
    loadContextOptions()
  } else {
    // 关闭时增加 requestId 使任何进行中的请求失效
    requestId++
    resetState()
  }
})

onUnmounted(() => {
  // 组件销毁时使所有请求失效
  requestId++
})
</script>
