<template>
  <div v-if="show" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg">
      <!-- 头部 -->
      <div class="flex items-center justify-between p-6 border-b border-gray-200">
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
      <div class="p-6 space-y-4">
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

        <!-- 写作要求输入 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            写作要求 <span class="text-gray-400 font-normal">(可选)</span>
          </label>
          <textarea
            v-model="writingNotes"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
            rows="4"
            placeholder="输入额外的写作要求，如风格偏好、情节重点、情绪基调等..."
          ></textarea>
          <p class="mt-1 text-xs text-gray-500">
            添加写作要求可以让生成的内容更符合您的预期
          </p>
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
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
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  show: boolean
  chapterNumber: number
  chapterTitle?: string
  chapterSummary?: string
}

const props = defineProps<Props>()

const emit = defineEmits(['close', 'generate'])

const writingNotes = ref('')

// 关闭弹窗时清空输入
watch(() => props.show, (newVal) => {
  if (!newVal) {
    writingNotes.value = ''
  }
})

const handleGenerate = () => {
  emit('generate', {
    chapterNumber: props.chapterNumber,
    writingNotes: writingNotes.value.trim() || undefined
  })
}
</script>
