<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">章节大纲</h2>
        <p class="text-sm text-slate-500">故事结构与章节节奏一目了然</p>
      </div>
      <div v-if="editable" class="flex items-center gap-2">
        <button
          type="button"
          class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg"
          @click="openAddModal"
        >
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
          </svg>
          新增章节
        </button>
      </div>
    </div>

    <!-- 有卷分组时显示分组视图 -->
    <template v-if="hasMultipleVolumes && outline.length">
      <div v-for="group in volumeGroups" :key="group.volume?.id ?? 'unassigned'" class="space-y-4">
        <!-- 卷标题（可折叠） -->
        <div
          @click="toggleVolume(group.volume?.id ?? null)"
          class="flex items-center gap-3 py-2 px-4 rounded-lg cursor-pointer hover:bg-slate-50 transition-colors border border-slate-200 bg-white"
        >
          <svg
            :class="['w-5 h-5 text-slate-500 transition-transform', isVolumeExpanded(group.volume?.id ?? null) ? 'rotate-90' : '']"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"></path>
          </svg>
          <span :class="['font-semibold', group.volume ? 'text-indigo-700' : 'text-slate-500']">
            {{ getVolumeTitle(group) }}
          </span>
          <span class="text-sm text-slate-400 ml-auto">{{ group.chapters.length }}章</span>
        </div>
        <!-- 卷内章节列表 -->
        <ol v-show="isVolumeExpanded(group.volume?.id ?? null)" class="relative border-l border-slate-200 ml-3 space-y-8 pl-4">
          <li
            v-for="chapter in group.chapters"
            :key="chapter.chapter_number"
            class="ml-6 group"
          >
            <span class="absolute -left-3 mt-1 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500 text-white text-xs font-semibold">
              {{ chapter.chapter_number }}
            </span>
            <div class="bg-white/95 rounded-2xl border border-slate-200 shadow-sm p-5 relative">
              <!-- 卡片右上角操作按钮 -->
              <div v-if="editable" class="absolute top-4 right-4 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  type="button"
                  class="p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                  title="编辑章节"
                  @click="openEditModal(getIndexByChapterNumber(chapter.chapter_number))">
                  <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                    <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
                  </svg>
                </button>
                <button
                  type="button"
                  class="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  title="删除章节"
                  @click="confirmDelete(getIndexByChapterNumber(chapter.chapter_number))">
                  <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
                  </svg>
                </button>
              </div>

              <div class="flex items-center justify-between gap-4 pr-20">
                <h3 class="text-lg font-semibold text-slate-900">{{ chapter.title || `第${chapter.chapter_number}章` }}</h3>
                <span class="text-xs text-slate-400">#{{ chapter.chapter_number }}</span>
              </div>
              <p class="mt-3 text-sm text-slate-600 leading-6 whitespace-pre-line">{{ chapter.summary || '暂无摘要' }}</p>
            </div>
          </li>
        </ol>
      </div>
    </template>

    <!-- 无卷分组时显示扁平列表 -->
    <ol v-else-if="outline.length" class="relative border-l border-slate-200 ml-3 space-y-8">
      <li
        v-for="(chapter, index) in outline"
        :key="chapter.chapter_number"
        class="ml-6 group"
      >
        <span class="absolute -left-3 mt-1 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500 text-white text-xs font-semibold">
          {{ chapter.chapter_number }}
        </span>
        <div class="bg-white/95 rounded-2xl border border-slate-200 shadow-sm p-5 relative">
          <!-- 卡片右上角操作按钮 -->
          <div v-if="editable" class="absolute top-4 right-4 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              type="button"
              class="p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
              title="编辑章节"
              @click="openEditModal(index)">
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
              </svg>
            </button>
            <button
              type="button"
              class="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              title="删除章节"
              @click="confirmDelete(index)">
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>

          <div class="flex items-center justify-between gap-4 pr-20">
            <h3 class="text-lg font-semibold text-slate-900">{{ chapter.title || `第${chapter.chapter_number}章` }}</h3>
            <span class="text-xs text-slate-400">#{{ chapter.chapter_number }}</span>
          </div>
          <p class="mt-3 text-sm text-slate-600 leading-6 whitespace-pre-line">{{ chapter.summary || '暂无摘要' }}</p>
        </div>
      </li>
    </ol>

    <!-- 无章节时的空状态 -->
    <div v-else class="text-center py-8 text-slate-400 text-sm">暂无章节大纲</div>

    <!-- 单章节编辑弹窗 -->
    <SingleChapterOutlineModal
      :show="showModal"
      :outline="editingOutline"
      :is-new="isNewOutline"
      :next-chapter-number="nextChapterNumber"
      :volumes="volumes"
      :existing-chapter-numbers="existingChapterNumbers"
      @close="closeModal"
      @save="handleSave"
    />

    <!-- 删除确认弹窗 -->
    <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-center items-center" @click.self="showDeleteConfirm = false">
      <div class="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">确认删除</h3>
        <p class="text-gray-600 mb-6">确定要删除「{{ deletingChapterTitle }}」吗？此操作无法撤销。</p>
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
import { computed, ref, watch } from 'vue'
import SingleChapterOutlineModal from '@/components/SingleChapterOutlineModal.vue'
import type { Volume } from '@/api/novel'

interface OutlineItem {
  chapter_number: number
  title: string
  summary: string
  volume_id?: number | null
}

interface VolumeGroup {
  volume: Volume | null
  chapters: OutlineItem[]
}

const props = defineProps<{
  outline: OutlineItem[]
  volumes?: Volume[]
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
  (e: 'add'): void
  (e: 'update-outline', outline: OutlineItem[]): void
}>()

// Modal 状态
const showModal = ref(false)
const editingOutline = ref<OutlineItem | null>(null)
const editingIndex = ref<number>(-1)
const isNewOutline = ref(false)
const expandedVolumes = ref<Set<number | null>>(new Set([null]))

// 下一个章节号
const nextChapterNumber = computed(() => {
  if (props.outline.length === 0) return 1
  return Math.max(...props.outline.map(o => o.chapter_number)) + 1
})

// 现有章节号列表（用于重复检测）
const existingChapterNumbers = computed(() => {
  return props.outline.map(o => o.chapter_number)
})

// 按卷分组章节
const volumeGroups = computed<VolumeGroup[]>(() => {
  const outlines = props.outline || []
  const volumes = props.volumes || []

  // 创建卷ID到卷对象的映射
  const volumeMap = new Map<number, Volume>()
  for (const vol of volumes) {
    volumeMap.set(vol.id, vol)
  }

  // 按卷分组
  const groups = new Map<number | null, OutlineItem[]>()

  for (const chapter of outlines) {
    const volumeId = chapter.volume_id ?? null
    if (!groups.has(volumeId)) {
      groups.set(volumeId, [])
    }
    groups.get(volumeId)!.push(chapter)
  }

  // 转换为数组并排序
  const result: VolumeGroup[] = []

  // 先添加有卷分配的组（按卷号排序）
  const volumeEntries = [...groups.entries()]
    .filter(([id]) => id !== null)
    .sort(([a], [b]) => {
      const volA = volumeMap.get(a as number)
      const volB = volumeMap.get(b as number)
      return (volA?.volume_number || 0) - (volB?.volume_number || 0)
    })

  for (const [volumeId, chapters] of volumeEntries) {
    const volume = volumeMap.get(volumeId as number) || null
    result.push({
      volume,
      chapters: chapters.sort((a, b) => a.chapter_number - b.chapter_number)
    })
  }

  // 最后添加未分配的组
  const unassigned = groups.get(null)
  if (unassigned && unassigned.length > 0) {
    result.push({
      volume: null,
      chapters: unassigned.sort((a, b) => a.chapter_number - b.chapter_number)
    })
  }

  return result
})

// 是否有多个卷（用于决定是否显示卷分组UI）
const hasMultipleVolumes = computed(() => {
  return volumeGroups.value.length > 1 || (props.volumes?.length || 0) > 0
})

// 切换卷的展开/折叠状态
const toggleVolume = (volumeId: number | null) => {
  if (expandedVolumes.value.has(volumeId)) {
    expandedVolumes.value.delete(volumeId)
  } else {
    expandedVolumes.value.add(volumeId)
  }
  expandedVolumes.value = new Set(expandedVolumes.value)
}

// 检查卷是否展开
const isVolumeExpanded = (volumeId: number | null) => {
  return expandedVolumes.value.has(volumeId)
}

// 获取卷的显示名称
const getVolumeTitle = (group: VolumeGroup) => {
  if (group.volume) {
    return `第${group.volume.volume_number}卷 ${group.volume.title}`
  }
  return '未分配章节'
}

// 当卷列表变化时，自动展开所有卷
watch(
  () => props.volumes,
  (newVolumes) => {
    if (newVolumes) {
      for (const vol of newVolumes) {
        expandedVolumes.value.add(vol.id)
      }
      expandedVolumes.value = new Set(expandedVolumes.value)
    }
  },
  { immediate: true }
)

// 根据 chapter_number 找到其在 outline 数组中的 index
const getIndexByChapterNumber = (chapterNumber: number) => {
  return props.outline.findIndex(o => o.chapter_number === chapterNumber)
}

// 删除确认状态
const showDeleteConfirm = ref(false)
const deletingIndex = ref<number>(-1)
const deletingChapterTitle = computed(() => {
  if (deletingIndex.value >= 0 && deletingIndex.value < props.outline.length) {
    const chapter = props.outline[deletingIndex.value]
    return chapter?.title || `第${chapter?.chapter_number}章`
  }
  return ''
})

const openAddModal = () => {
  editingOutline.value = null
  editingIndex.value = -1
  isNewOutline.value = true
  showModal.value = true
}

const openEditModal = (index: number) => {
  editingOutline.value = props.outline[index]
  editingIndex.value = index
  isNewOutline.value = false
  showModal.value = true
}

const closeModal = () => {
  showModal.value = false
  editingOutline.value = null
  editingIndex.value = -1
}

const handleSave = (outlineItem: OutlineItem) => {
  const newOutline = [...props.outline]

  if (isNewOutline.value) {
    newOutline.push(outlineItem)
    // 按章节号排序
    newOutline.sort((a, b) => a.chapter_number - b.chapter_number)
  } else if (editingIndex.value >= 0) {
    newOutline[editingIndex.value] = outlineItem
  }

  emit('update-outline', newOutline)
  closeModal()
}

const confirmDelete = (index: number) => {
  deletingIndex.value = index
  showDeleteConfirm.value = true
}

const executeDelete = () => {
  if (deletingIndex.value >= 0) {
    const newOutline = props.outline.filter((_, i) => i !== deletingIndex.value)
    emit('update-outline', newOutline)
  }
  showDeleteConfirm.value = false
  deletingIndex.value = -1
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChapterOutlineSection'
})
</script>
