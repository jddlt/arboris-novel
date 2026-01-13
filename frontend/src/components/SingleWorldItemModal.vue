<template>
  <div v-if="show" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4">
      <div class="p-6 border-b border-gray-200">
        <h3 class="text-xl font-semibold text-gray-800">{{ isNew ? `新增${itemLabel}` : `编辑${itemLabel}` }}</h3>
        <p class="text-sm text-gray-500 mt-1">{{ isNew ? `添加一个新的${itemLabel}` : `编辑「${localItem.name}」` }}</p>
      </div>

      <div class="p-6 space-y-5">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">名称 *</label>
          <input
            type="text"
            v-model="localItem.name"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
            :placeholder="`${itemLabel}名称`"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">描述</label>
          <textarea
            v-model="localItem.description"
            rows="4"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition resize-none"
            :placeholder="`关于这个${itemLabel}的详细描述...`"
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
          :disabled="!localItem.name?.trim()"
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

interface WorldItem {
  name?: string
  description?: string
}

const props = defineProps<{
  show: boolean
  item: WorldItem | null
  isNew: boolean
  itemLabel: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', item: WorldItem): void
}>()

const emptyItem = (): WorldItem => ({
  name: '',
  description: ''
})

const localItem = ref<WorldItem>(emptyItem())

watch(() => props.show, (visible) => {
  if (visible) {
    if (props.item) {
      localItem.value = JSON.parse(JSON.stringify(props.item))
    } else {
      localItem.value = emptyItem()
    }
  }
}, { immediate: true })

const save = () => {
  if (!localItem.value.name?.trim()) return
  emit('save', JSON.parse(JSON.stringify(localItem.value)))
}
</script>
