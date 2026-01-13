<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">主要角色</h2>
        <p class="text-sm text-slate-500">了解故事中核心人物的目标与个性</p>
      </div>
      <button
        v-if="editable"
        type="button"
        class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors"
        @click="openAddModal">
        <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
        </svg>
        新增角色
      </button>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <article
        v-for="(character, index) in characters"
        :key="index"
        class="bg-white/95 rounded-2xl border border-slate-200 shadow-sm hover:shadow-lg transition-all duration-300 group relative">

        <!-- 卡片右上角操作按钮 -->
        <div v-if="editable" class="absolute top-4 right-4 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            type="button"
            class="p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
            title="编辑角色"
            @click="openEditModal(index)">
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
              <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
            </svg>
          </button>
          <button
            type="button"
            class="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            title="删除角色"
            @click="confirmDelete(index)">
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>

        <div class="p-6">
          <div class="flex flex-col sm:flex-row sm:items-center gap-4 mb-4">
            <div class="w-16 h-16 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-lg font-semibold">
              {{ character.name?.slice(0, 1) || '角' }}
            </div>
            <div>
              <h3 class="text-xl font-bold text-slate-900">{{ character.name || '未命名角色' }}</h3>
              <p v-if="character.identity" class="text-sm text-indigo-500 font-medium">{{ character.identity }}</p>
            </div>
          </div>
          <dl class="space-y-3 text-sm text-slate-600">
            <div v-if="character.personality">
              <dt class="font-semibold text-slate-800 mb-1">性格</dt>
              <dd class="leading-6">{{ character.personality }}</dd>
            </div>
            <div v-if="character.goals">
              <dt class="font-semibold text-slate-800 mb-1">目标</dt>
              <dd class="leading-6">{{ character.goals }}</dd>
            </div>
            <div v-if="character.abilities">
              <dt class="font-semibold text-slate-800 mb-1">能力</dt>
              <dd class="leading-6">{{ character.abilities }}</dd>
            </div>
            <div v-if="character.relationship_to_protagonist">
              <dt class="font-semibold text-slate-800 mb-1">与主角的关系</dt>
              <dd class="leading-6">{{ character.relationship_to_protagonist }}</dd>
            </div>
          </dl>
        </div>
      </article>
      <div v-if="!characters.length" class="bg-white/95 rounded-2xl border border-dashed border-slate-300 p-10 text-center text-slate-400">
        暂无角色信息
      </div>
    </div>

    <!-- 单角色编辑弹窗 -->
    <SingleCharacterModal
      :show="showModal"
      :character="editingCharacter"
      :is-new="isNewCharacter"
      @close="closeModal"
      @save="handleSave"
    />

    <!-- 删除确认弹窗 -->
    <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="showDeleteConfirm = false">
      <div class="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">确认删除</h3>
        <p class="text-gray-600 mb-6">确定要删除角色「{{ deletingCharacterName }}」吗？此操作无法撤销。</p>
        <div class="flex justify-end gap-3">
          <button
            @click="showDeleteConfirm = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-100 transition"
          >
            取消
          </button>
          <button
            @click="executeDelete"
            class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, defineEmits, defineProps } from 'vue'
import SingleCharacterModal from '@/components/SingleCharacterModal.vue'

interface CharacterItem {
  name?: string
  identity?: string
  personality?: string
  goals?: string
  abilities?: string
  relationship_to_protagonist?: string
}

const props = defineProps<{
  data: { characters?: CharacterItem[] } | null
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
  (e: 'update-characters', characters: CharacterItem[]): void
}>()

const characters = computed(() => props.data?.characters || [])

// Modal 状态
const showModal = ref(false)
const editingCharacter = ref<CharacterItem | null>(null)
const editingIndex = ref<number>(-1)
const isNewCharacter = ref(false)

// 删除确认状态
const showDeleteConfirm = ref(false)
const deletingIndex = ref<number>(-1)
const deletingCharacterName = computed(() => {
  if (deletingIndex.value >= 0 && deletingIndex.value < characters.value.length) {
    return characters.value[deletingIndex.value]?.name || '未命名角色'
  }
  return ''
})

const openAddModal = () => {
  editingCharacter.value = null
  editingIndex.value = -1
  isNewCharacter.value = true
  showModal.value = true
}

const openEditModal = (index: number) => {
  editingCharacter.value = characters.value[index]
  editingIndex.value = index
  isNewCharacter.value = false
  showModal.value = true
}

const closeModal = () => {
  showModal.value = false
  editingCharacter.value = null
  editingIndex.value = -1
}

const handleSave = (character: CharacterItem) => {
  const newCharacters = [...characters.value]

  if (isNewCharacter.value) {
    newCharacters.push(character)
  } else if (editingIndex.value >= 0) {
    newCharacters[editingIndex.value] = character
  }

  emit('update-characters', newCharacters)
  closeModal()
}

const confirmDelete = (index: number) => {
  deletingIndex.value = index
  showDeleteConfirm.value = true
}

const executeDelete = () => {
  if (deletingIndex.value >= 0) {
    const newCharacters = characters.value.filter((_, i) => i !== deletingIndex.value)
    emit('update-characters', newCharacters)
  }
  showDeleteConfirm.value = false
  deletingIndex.value = -1
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'CharactersSection'
})
</script>
