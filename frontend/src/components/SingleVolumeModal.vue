<template>
  <div v-if="show" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
      <div class="p-6 border-b border-gray-200">
        <h3 class="text-xl font-semibold text-gray-800">{{ isNew ? '新增卷' : '编辑卷' }}</h3>
        <p class="text-sm text-gray-500 mt-1">{{ isNew ? '添加新的卷结构' : `编辑第${localVolume.volume_number}卷` }}</p>
      </div>

      <div class="p-6 space-y-5">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">卷序号 *</label>
            <input
              type="number"
              v-model.number="localVolume.volume_number"
              min="1"
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
              placeholder="1"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">状态</label>
            <select
              v-model="localVolume.status"
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
            >
              <option value="planned">📋 规划中</option>
              <option value="in_progress">📝 写作中</option>
              <option value="completed">✅ 已完成</option>
            </select>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">卷标题 *</label>
          <input
            type="text"
            v-model="localVolume.title"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
            placeholder="如：序章·命运的起点"
          />
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">起始章节 *</label>
            <input
              type="number"
              v-model.number="localVolume.chapter_start"
              min="1"
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
              placeholder="1"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">结束章节 *</label>
            <input
              type="number"
              v-model.number="localVolume.chapter_end"
              min="1"
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
              placeholder="10"
            />
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">卷概要</label>
          <textarea
            v-model="localVolume.summary"
            rows="3"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition resize-none"
            placeholder="描述本卷的主要内容和发展..."
          ></textarea>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">核心冲突</label>
          <input
            type="text"
            v-model="localVolume.core_conflict"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
            placeholder="本卷的主要矛盾冲突..."
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">高潮点</label>
          <input
            type="text"
            v-model="localVolume.climax"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
            placeholder="本卷的高潮情节..."
          />
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
  show: boolean
  volume: Volume | null
  isNew: boolean
  nextVolumeNumber?: number
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', volume: Volume): void
}>()

const emptyVolume = (): Volume => ({
  volume_number: props.nextVolumeNumber || 1,
  title: '',
  chapter_start: 1,
  chapter_end: 10,
  summary: '',
  core_conflict: '',
  climax: '',
  status: 'planned',
})

const localVolume = ref<Volume>(emptyVolume())

const isValid = computed(() => {
  return (
    localVolume.value.volume_number &&
    localVolume.value.volume_number > 0 &&
    localVolume.value.title?.trim() &&
    localVolume.value.chapter_start &&
    localVolume.value.chapter_start > 0 &&
    localVolume.value.chapter_end &&
    localVolume.value.chapter_end >= localVolume.value.chapter_start
  )
})

watch(() => props.show, (visible) => {
  if (visible) {
    if (props.volume) {
      localVolume.value = JSON.parse(JSON.stringify(props.volume))
    } else {
      localVolume.value = {
        volume_number: props.nextVolumeNumber || 1,
        title: '',
        chapter_start: 1,
        chapter_end: 10,
        summary: '',
        core_conflict: '',
        climax: '',
        status: 'planned',
      }
    }
  }
}, { immediate: true })

const save = () => {
  if (!isValid.value) return
  emit('save', JSON.parse(JSON.stringify(localVolume.value)))
}
</script>
