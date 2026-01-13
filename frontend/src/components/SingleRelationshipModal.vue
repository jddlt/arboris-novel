<template>
  <div v-if="show" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4">
      <div class="p-6 border-b border-gray-200">
        <h3 class="text-xl font-semibold text-gray-800">{{ isNew ? '新增关系' : '编辑关系' }}</h3>
        <p class="text-sm text-gray-500 mt-1">定义两个角色之间的关系</p>
      </div>

      <div class="p-6 space-y-5">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">角色 A *</label>
            <input
              type="text"
              v-model="localRelationship.character_from"
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
              placeholder="如：林远"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">角色 B *</label>
            <input
              type="text"
              v-model="localRelationship.character_to"
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
              placeholder="如：苏晴"
            />
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">关系描述</label>
          <textarea
            v-model="localRelationship.description"
            rows="4"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition resize-none"
            placeholder="描述这两个角色之间的关系、情感纽带或冲突..."
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

interface Relationship {
  character_from?: string
  character_to?: string
  description?: string
}

const props = defineProps<{
  show: boolean
  relationship: Relationship | null
  isNew: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', relationship: Relationship): void
}>()

const emptyRelationship = (): Relationship => ({
  character_from: '',
  character_to: '',
  description: ''
})

const localRelationship = ref<Relationship>(emptyRelationship())

const canSave = computed(() =>
  localRelationship.value.character_from?.trim() &&
  localRelationship.value.character_to?.trim()
)

watch(() => props.show, (visible) => {
  if (visible) {
    if (props.relationship) {
      localRelationship.value = JSON.parse(JSON.stringify(props.relationship))
    } else {
      localRelationship.value = emptyRelationship()
    }
  }
}, { immediate: true })

const save = () => {
  if (!canSave.value) return
  emit('save', JSON.parse(JSON.stringify(localRelationship.value)))
}
</script>
