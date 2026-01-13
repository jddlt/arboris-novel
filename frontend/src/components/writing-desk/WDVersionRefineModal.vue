<template>
  <div v-if="show" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
      <!-- 头部 -->
      <div class="flex items-center justify-between p-6 border-b border-gray-200 flex-shrink-0">
        <div>
          <h3 class="text-lg font-semibold text-gray-900">微调版本</h3>
          <p class="text-sm text-gray-500 mt-1">基于当前版本内容进行修改优化</p>
        </div>
        <button
          @click="$emit('close')"
          :disabled="isRefining"
          class="text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-50"
        >
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </div>

      <!-- 内容 -->
      <div class="p-6 space-y-4 overflow-y-auto flex-1">
        <!-- 当前版本预览 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            当前版本内容
            <span class="text-gray-400 font-normal ml-2">版本 {{ versionIndex + 1 }}</span>
          </label>
          <div class="bg-gray-50 rounded-lg p-4 max-h-48 overflow-y-auto">
            <p class="text-sm text-gray-700 whitespace-pre-wrap line-clamp-6">{{ cleanContent }}</p>
            <p v-if="cleanContent.length > 300" class="text-xs text-gray-400 mt-2">
              ...共 {{ cleanContent.length }} 字
            </p>
          </div>
        </div>

        <!-- 修改指令输入 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            修改指令 <span class="text-red-500">*</span>
          </label>
          <textarea
            v-model="refinementPrompt"
            :disabled="isRefining"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-amber-500 resize-none disabled:opacity-50 disabled:bg-gray-50"
            rows="4"
            placeholder="描述您希望如何修改这个版本，例如：&#10;• 增加更多环境描写&#10;• 调整对话的语气，使之更加紧张&#10;• 补充角色的心理活动&#10;• 缩短篇幅，更加精炼"
          ></textarea>
          <p class="mt-1 text-xs text-gray-500">
            清晰描述修改方向，AI 将基于原内容生成微调后的新版本
          </p>
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="flex items-center justify-end gap-3 p-6 border-t border-gray-200 flex-shrink-0">
        <button
          @click="$emit('close')"
          :disabled="isRefining"
          class="px-4 py-2 text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg transition-colors disabled:opacity-50"
        >
          取消
        </button>
        <button
          @click="handleRefine"
          :disabled="!refinementPrompt.trim() || isRefining"
          class="px-6 py-2 bg-amber-600 text-white hover:bg-amber-700 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          <svg v-if="isRefining" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
          </svg>
          <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
          </svg>
          {{ isRefining ? '微调中...' : '开始微调' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface Props {
  show: boolean
  versionIndex: number
  versionContent: string
  isRefining?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits(['close', 'refine'])

const refinementPrompt = ref('')

// 清理版本内容用于显示
const cleanContent = computed(() => {
  if (!props.versionContent) return ''
  let content = props.versionContent

  try {
    const parsed = JSON.parse(content)
    if (parsed && typeof parsed === 'object' && parsed.content) {
      content = parsed.content
    }
  } catch {
    // not JSON
  }

  content = content.replace(/^"|"$/g, '')
  content = content.replace(/\\n/g, '\n')
  content = content.replace(/\\"/g, '"')
  content = content.replace(/\\t/g, '\t')
  content = content.replace(/\\\\/g, '\\')

  return content
})

// 关闭弹窗时清空输入
watch(() => props.show, (newVal) => {
  if (!newVal) {
    refinementPrompt.value = ''
  }
})

const handleRefine = () => {
  if (!refinementPrompt.value.trim()) return

  emit('refine', {
    versionIndex: props.versionIndex,
    prompt: refinementPrompt.value.trim()
  })
}
</script>
