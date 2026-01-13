<template>
  <div v-if="show" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
      <div class="p-6 border-b border-gray-200">
        <h3 class="text-xl font-semibold text-gray-800">{{ isNew ? '新增伏笔' : '编辑伏笔' }}</h3>
        <p class="text-sm text-gray-500 mt-1">{{ isNew ? '添加需要追踪的情节伏笔' : `编辑「${localThread.title}」` }}</p>
      </div>

      <div class="p-6 space-y-5">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">伏笔标题 *</label>
          <input
            type="text"
            v-model="localThread.title"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
            placeholder="如：主角身世之谜"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">详细描述</label>
          <textarea
            v-model="localThread.description"
            rows="3"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition resize-none"
            placeholder="描述伏笔的内容和目的..."
          ></textarea>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">埋设章节 *</label>
            <input
              type="number"
              v-model.number="localThread.plant_chapter"
              min="1"
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
              placeholder="1"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">预计揭示章节 *</label>
            <input
              type="number"
              v-model.number="localThread.reveal_chapter"
              min="1"
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
              placeholder="25"
            />
          </div>
        </div>

        <div v-if="!isNew">
          <label class="block text-sm font-medium text-gray-700 mb-2">状态</label>
          <select
            v-model="localThread.status"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
          >
            <option value="active">🔮 活跃（待回收）</option>
            <option value="revealed">✅ 已揭示</option>
            <option value="abandoned">🚫 已弃用</option>
          </select>
        </div>

        <!-- 线索列表 -->
        <div v-if="!isNew && localThread.clues && localThread.clues.length > 0">
          <label class="block text-sm font-medium text-gray-700 mb-2">已埋线索</label>
          <div class="space-y-2">
            <div
              v-for="(clue, index) in localThread.clues"
              :key="index"
              class="flex items-start gap-2 bg-slate-50 p-3 rounded-lg"
            >
              <span class="text-xs text-indigo-600 font-medium whitespace-nowrap">第{{ clue.chapter }}章</span>
              <span class="text-sm text-slate-600 flex-1">{{ clue.content }}</span>
              <button
                type="button"
                class="text-gray-400 hover:text-red-600 flex-shrink-0"
                @click="removeClue(index)"
              >
                <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- 添加新线索 -->
        <div v-if="!isNew" class="border-t border-gray-200 pt-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">添加新线索</label>
          <div class="flex gap-2">
            <input
              type="number"
              v-model.number="newClue.chapter"
              min="1"
              class="w-24 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition text-sm"
              placeholder="章节"
            />
            <input
              type="text"
              v-model="newClue.content"
              class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition text-sm"
              placeholder="线索内容..."
            />
            <button
              type="button"
              @click="addClue"
              :disabled="!newClue.chapter || !newClue.content?.trim()"
              class="px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition disabled:opacity-50"
            >
              添加
            </button>
          </div>
        </div>
      </div>

      <div class="px-6 py-4 bg-gray-50 rounded-b-xl flex justify-end space-x-3">
        <button
          @click="$emit('close')"
          class="px-5 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-100 transition"
        >
          取消
        </button>
        <button
          @click="save"
          :disabled="!isValid"
          class="px-5 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ isNew ? '添加' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, defineProps, defineEmits } from 'vue'

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
  show: boolean
  thread: ForeshadowingThread | null
  isNew: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', thread: ForeshadowingThread): void
}>()

const emptyThread = (): ForeshadowingThread => ({
  title: '',
  description: '',
  plant_chapter: 1,
  reveal_chapter: 10,
  clues: [],
  status: 'active',
})

const localThread = ref<ForeshadowingThread>(emptyThread())
const newClue = ref<{ chapter?: number; content?: string }>({})

const isValid = computed(() => {
  return (
    localThread.value.title?.trim() &&
    localThread.value.plant_chapter &&
    localThread.value.plant_chapter > 0 &&
    localThread.value.reveal_chapter &&
    localThread.value.reveal_chapter >= localThread.value.plant_chapter
  )
})

watch(() => props.show, (visible) => {
  if (visible) {
    if (props.thread) {
      localThread.value = JSON.parse(JSON.stringify(props.thread))
    } else {
      localThread.value = emptyThread()
    }
    newClue.value = {}
  }
}, { immediate: true })

const addClue = () => {
  if (!newClue.value.chapter || !newClue.value.content?.trim()) return
  if (!localThread.value.clues) {
    localThread.value.clues = []
  }
  localThread.value.clues.push({
    chapter: newClue.value.chapter,
    content: newClue.value.content.trim(),
  })
  localThread.value.clues.sort((a, b) => a.chapter - b.chapter)
  newClue.value = {}
}

const removeClue = (index: number) => {
  if (localThread.value.clues) {
    localThread.value.clues.splice(index, 1)
  }
}

const save = () => {
  if (!isValid.value) return
  emit('save', JSON.parse(JSON.stringify(localThread.value)))
}
</script>
