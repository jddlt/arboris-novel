<template>
  <div v-if="show" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-xl mx-4">
      <div class="p-6 border-b border-gray-200">
        <h3 class="text-xl font-semibold text-gray-800">{{ isNew ? '新增角色' : '编辑角色' }}</h3>
        <p class="text-sm text-gray-500 mt-1">{{ isNew ? '创建一个新的故事角色' : `编辑角色：${localCharacter.name || '未命名'}` }}</p>
      </div>

      <div class="p-6 space-y-5 max-h-[60vh] overflow-y-auto">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">姓名 *</label>
          <input
            type="text"
            v-model="localCharacter.name"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
            placeholder="角色名称"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">身份</label>
          <input
            type="text"
            v-model="localCharacter.identity"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
            placeholder="角色的身份背景，如：王国骑士、流浪法师"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">性格</label>
          <textarea
            v-model="localCharacter.personality"
            rows="3"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition resize-none"
            placeholder="角色的性格特征"
          ></textarea>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">目标</label>
          <textarea
            v-model="localCharacter.goals"
            rows="3"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition resize-none"
            placeholder="角色的目标或欲望"
          ></textarea>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">能力</label>
          <textarea
            v-model="localCharacter.abilities"
            rows="2"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition resize-none"
            placeholder="角色拥有的能力或技能"
          ></textarea>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">与主角关系</label>
          <input
            type="text"
            v-model="localCharacter.relationship_to_protagonist"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
            placeholder="如：挚友、宿敌、导师"
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
          :disabled="!localCharacter.name?.trim()"
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

interface Character {
  name?: string
  identity?: string
  personality?: string
  goals?: string
  abilities?: string
  relationship_to_protagonist?: string
}

const props = defineProps<{
  show: boolean
  character: Character | null
  isNew: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', character: Character): void
}>()

const emptyCharacter = (): Character => ({
  name: '',
  identity: '',
  personality: '',
  goals: '',
  abilities: '',
  relationship_to_protagonist: ''
})

const localCharacter = ref<Character>(emptyCharacter())

watch(() => props.show, (visible) => {
  if (visible) {
    if (props.character) {
      localCharacter.value = JSON.parse(JSON.stringify(props.character))
    } else {
      localCharacter.value = emptyCharacter()
    }
  }
}, { immediate: true })

const save = () => {
  if (!localCharacter.value.name?.trim()) return
  emit('save', JSON.parse(JSON.stringify(localCharacter.value)))
}
</script>
