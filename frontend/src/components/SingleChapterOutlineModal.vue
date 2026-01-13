<template>
  <div v-if="show" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-xl mx-4">
      <div class="p-6 border-b border-gray-200">
        <h3 class="text-xl font-semibold text-gray-800">{{ isNew ? '新增章节' : '编辑章节' }}</h3>
        <p class="text-sm text-gray-500 mt-1">{{ isNew ? '添加新的章节大纲' : `编辑第 ${localOutline.chapter_number} 章` }}</p>
      </div>

      <div class="p-6 space-y-5">
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
          :disabled="!localOutline.title?.trim()"
          class="px-5 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ isNew ? '添加' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, defineProps, defineEmits } from 'vue'

interface ChapterOutline {
  chapter_number: number
  title: string
  summary: string
}

const props = defineProps<{
  show: boolean
  outline: ChapterOutline | null
  isNew: boolean
  nextChapterNumber?: number
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', outline: ChapterOutline): void
}>()

const emptyOutline = (): ChapterOutline => ({
  chapter_number: props.nextChapterNumber || 1,
  title: '',
  summary: ''
})

const localOutline = ref<ChapterOutline>(emptyOutline())

watch(() => props.show, (visible) => {
  if (visible) {
    if (props.outline) {
      localOutline.value = JSON.parse(JSON.stringify(props.outline))
    } else {
      localOutline.value = {
        chapter_number: props.nextChapterNumber || 1,
        title: '',
        summary: ''
      }
    }
  }
}, { immediate: true })

const save = () => {
  if (!localOutline.value.title?.trim()) return
  emit('save', JSON.parse(JSON.stringify(localOutline.value)))
}
</script>
