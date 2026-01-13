<template>
  <div v-if="show" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-xl mx-4">
      <div class="p-6 border-b border-gray-200">
        <h3 class="text-xl font-semibold text-gray-800">{{ isNew ? '新增章节' : '编辑章节' }}</h3>
        <p class="text-sm text-gray-500 mt-1">{{ isNew ? '添加新的章节大纲' : `编辑第 ${localOutline.chapter_number} 章` }}</p>
      </div>

      <div class="p-6 space-y-5">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">章节序号 *</label>
            <input
              type="number"
              v-model.number="localOutline.chapter_number"
              min="1"
              :class="[
                'w-full px-4 py-3 border rounded-lg focus:ring-2 transition',
                isDuplicateChapter
                  ? 'border-red-500 focus:ring-red-500 focus:border-red-500'
                  : 'border-gray-300 focus:ring-indigo-500 focus:border-indigo-500'
              ]"
              placeholder="1"
            />
            <p v-if="isDuplicateChapter" class="text-red-500 text-xs mt-1">该章节序号已存在</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">所属卷</label>
            <select
              v-model="localOutline.volume_id"
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition bg-white"
            >
              <option :value="null">未分配</option>
              <option v-for="vol in volumes" :key="vol.id" :value="vol.id">
                第{{ vol.volume_number }}卷 {{ vol.title }}
              </option>
            </select>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">章节标题 *</label>
          <input
            type="text"
            v-model="localOutline.title"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
            placeholder="如：意外的相遇"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">章节摘要</label>
          <textarea
            v-model="localOutline.summary"
            rows="6"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition resize-none"
            placeholder="简要描述本章发生的主要事件..."
          ></textarea>
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
          :disabled="!canSave"
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

interface Volume {
  id: number
  volume_number: number
  title: string
}

interface ChapterOutline {
  chapter_number: number
  title: string
  summary: string
  volume_id?: number | null
}

const props = defineProps<{
  show: boolean
  outline: ChapterOutline | null
  isNew: boolean
  nextChapterNumber?: number
  volumes?: Volume[]
  existingChapterNumbers?: number[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', outline: ChapterOutline): void
}>()

const emptyOutline = (): ChapterOutline => ({
  chapter_number: props.nextChapterNumber || 1,
  title: '',
  summary: '',
  volume_id: null
})

const localOutline = ref<ChapterOutline>(emptyOutline())

// 检测是否为重复章节号
const isDuplicateChapter = computed(() => {
  const num = localOutline.value.chapter_number
  if (!num || num < 1) return false
  const existing = props.existingChapterNumbers || []
  // 编辑模式下，允许保持原来的章节号
  if (!props.isNew && props.outline?.chapter_number === num) return false
  return existing.includes(num)
})

// 是否可以保存
const canSave = computed(() => {
  return localOutline.value.title?.trim() &&
         localOutline.value.chapter_number >= 1 &&
         !isDuplicateChapter.value
})

watch(() => props.show, (visible) => {
  if (visible) {
    if (props.outline) {
      localOutline.value = JSON.parse(JSON.stringify(props.outline))
    } else {
      localOutline.value = {
        chapter_number: props.nextChapterNumber || 1,
        title: '',
        summary: '',
        volume_id: null
      }
    }
  }
}, { immediate: true })

const save = () => {
  if (!canSave.value) return
  emit('save', JSON.parse(JSON.stringify(localOutline.value)))
}
</script>
