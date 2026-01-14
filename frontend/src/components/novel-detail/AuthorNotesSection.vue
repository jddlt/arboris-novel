<template>
  <div class="space-y-6">
    <!-- 内部 Tab 切换 -->
    <div class="flex items-center gap-4 border-b border-slate-200 pb-4">
      <button
        class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors"
        :class="activeTab === 'notes'
          ? 'bg-indigo-600 text-white shadow-md'
          : 'text-slate-600 hover:bg-slate-100'"
        @click="activeTab = 'notes'"
      >
        <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm3 1h6v1H7V5zm6 3H7v1h6V8zm-6 3h6v1H7v-1z" />
        </svg>
        作者备忘录
        <span v-if="notes.length" class="text-xs opacity-70">({{ notes.length }})</span>
      </button>
      <button
        class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors"
        :class="activeTab === 'states'
          ? 'bg-indigo-600 text-white shadow-md'
          : 'text-slate-600 hover:bg-slate-100'"
        @click="activeTab = 'states'"
      >
        <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
          <path fill-rule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3z" clip-rule="evenodd" />
        </svg>
        角色状态
        <span v-if="states.length" class="text-xs opacity-70">({{ states.length }})</span>
      </button>
    </div>

    <!-- 备忘录内容 -->
    <div v-if="activeTab === 'notes'">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h2 class="text-2xl font-bold text-slate-900">作者备忘录</h2>
          <p class="text-sm text-slate-500">记录写作笔记、角色秘密、风格提醒等信息</p>
        </div>
        <div v-if="editable" class="flex items-center gap-2">
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg"
            @click="openAddNoteModal"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
            </svg>
            新增备忘
          </button>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div v-if="notes.length" class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div class="bg-blue-50 rounded-xl p-4">
          <div class="text-2xl font-bold text-blue-600">{{ chapterNotes.length }}</div>
          <div class="text-sm text-blue-600/70">章节备忘</div>
        </div>
        <div class="bg-purple-50 rounded-xl p-4">
          <div class="text-2xl font-bold text-purple-600">{{ secretNotes.length }}</div>
          <div class="text-sm text-purple-600/70">角色秘密</div>
        </div>
        <div class="bg-amber-50 rounded-xl p-4">
          <div class="text-2xl font-bold text-amber-600">{{ styleNotes.length }}</div>
          <div class="text-sm text-amber-600/70">写作风格</div>
        </div>
        <div class="bg-slate-50 rounded-xl p-4">
          <div class="text-2xl font-bold text-slate-600">{{ globalNotes.length }}</div>
          <div class="text-sm text-slate-600/70">全局备忘</div>
        </div>
      </div>

      <!-- 类型筛选 -->
      <div class="flex flex-wrap gap-2 mb-4">
        <button
          v-for="filter in typeFilters"
          :key="filter.value"
          class="px-3 py-1.5 text-sm rounded-lg transition-colors"
          :class="activeNoteFilter === filter.value
            ? 'bg-indigo-600 text-white'
            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
          @click="activeNoteFilter = filter.value"
        >
          {{ filter.label }}
          <span v-if="getCountByType(filter.value)" class="ml-1 opacity-70">({{ getCountByType(filter.value) }})</span>
        </button>
      </div>

      <!-- 备忘列表 -->
      <div v-if="filteredNotes.length" class="space-y-3">
        <div
          v-for="note in filteredNotes"
          :key="note.id"
          class="bg-white/95 rounded-xl border border-slate-200 shadow-sm p-5 group relative"
          :class="{ 'opacity-50': !note.is_active }"
        >
          <!-- 操作按钮 -->
          <div v-if="editable" class="absolute top-4 right-4 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              type="button"
              class="p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
              title="编辑"
              @click="openEditNoteModal(note)"
            >
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
              </svg>
            </button>
            <button
              type="button"
              class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
              title="删除"
              @click="confirmDeleteNote(note)"
            >
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>

          <div class="pr-24">
            <div class="flex items-center gap-2 mb-2 flex-wrap">
              <span class="text-lg">{{ getTypeIcon(note.type) }}</span>
              <span
                class="text-xs px-2 py-0.5 rounded-full"
                :class="getTypeBadgeClass(note.type)"
              >
                {{ getTypeLabel(note.type) }}
              </span>
              <span v-if="note.volume_id" class="text-xs bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">
                {{ getVolumeName(note.volume_id) }}
              </span>
              <span v-if="note.chapter_number" class="text-xs text-slate-500">
                第{{ note.chapter_number }}章
              </span>
              <span v-if="!note.is_active" class="text-xs bg-slate-200 text-slate-500 px-2 py-0.5 rounded-full">
                已归档
              </span>
            </div>
            <h4 class="font-semibold text-slate-900 mb-2">{{ note.title }}</h4>
            <div class="text-sm text-slate-600 prose prose-sm prose-slate max-w-none" v-html="renderMarkdown(note.content)"></div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="text-center py-12 text-slate-400">
        <svg class="mx-auto h-12 w-12 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p>{{ activeNoteFilter === 'all' ? '暂无备忘录' : '该类型暂无备忘录' }}</p>
        <button
          v-if="editable"
          class="mt-4 text-indigo-600 hover:text-indigo-700"
          @click="openAddNoteModal"
        >
          添加第一条备忘
        </button>
      </div>
    </div>

    <!-- 角色状态内容 -->
    <div v-else-if="activeTab === 'states'">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h2 class="text-2xl font-bold text-slate-900">角色状态追踪</h2>
          <p class="text-sm text-slate-500">记录角色在各章节的属性变化（等级、装备、技能等）</p>
        </div>
        <div v-if="editable && characters.length" class="flex items-center gap-2">
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg"
            @click="openAddStateModal"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
            </svg>
            新增状态
          </button>
        </div>
      </div>

      <!-- 角色筛选 -->
      <div v-if="characters.length" class="flex flex-wrap gap-2 mb-4">
        <button
          class="px-3 py-1.5 text-sm rounded-lg transition-colors"
          :class="selectedCharacterId === null
            ? 'bg-indigo-600 text-white'
            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
          @click="selectCharacter(null)"
        >
          全部角色
        </button>
        <button
          v-for="char in characters"
          :key="char.id"
          class="px-3 py-1.5 text-sm rounded-lg transition-colors"
          :class="isCharacterSelected(char.id)
            ? 'bg-indigo-600 text-white'
            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
          @click="selectCharacter(char.id)"
        >
          {{ char.name }}
          <span v-if="getStateCountByCharacter(char.id)" class="ml-1 opacity-70">({{ getStateCountByCharacter(char.id) }})</span>
        </button>
      </div>

      <!-- 状态列表 -->
      <div v-if="filteredStates.length" class="space-y-4">
        <div
          v-for="state in filteredStates"
          :key="state.id"
          class="bg-white/95 rounded-xl border border-slate-200 shadow-sm p-5 group relative"
        >
          <!-- 操作按钮 -->
          <div v-if="editable" class="absolute top-4 right-4 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              type="button"
              class="p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
              title="编辑"
              @click="openEditStateModal(state)"
            >
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
              </svg>
            </button>
            <button
              type="button"
              class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
              title="删除"
              @click="confirmDeleteState(state)"
            >
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>

          <div class="pr-24">
            <div class="flex items-center gap-3 mb-3">
              <span class="text-lg">👤</span>
              <span class="font-semibold text-slate-900">{{ state.character_name || getCharacterName(state.character_id) }}</span>
              <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                第{{ state.chapter_number }}章
              </span>
            </div>

            <!-- 状态数据展示 -->
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-3">
              <div
                v-for="(value, key) in state.data"
                :key="key"
                class="bg-slate-50 rounded-lg px-3 py-2"
              >
                <div class="text-xs text-slate-500">{{ key }}</div>
                <div class="font-medium text-slate-800">{{ formatValue(value) }}</div>
              </div>
            </div>

            <!-- 变更备注 -->
            <p v-if="state.change_note" class="text-sm text-slate-500 italic">
              📝 {{ state.change_note }}
            </p>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="text-center py-12 text-slate-400">
        <svg class="mx-auto h-12 w-12 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <p>{{ selectedCharacterId ? '该角色暂无状态记录' : '暂无角色状态记录' }}</p>
        <button
          v-if="editable && characters.length"
          class="mt-4 text-indigo-600 hover:text-indigo-700"
          @click="openAddStateModal"
        >
          记录第一条状态
        </button>
        <p v-else-if="!characters.length" class="mt-2 text-sm">
          请先在"主要角色"中添加角色
        </p>
      </div>
    </div>

    <!-- 添加/编辑备忘弹窗 -->
    <n-modal v-model:show="showNoteModal" preset="dialog" :title="editingNote ? '编辑备忘' : '新增备忘'" style="width: 600px;">
      <n-form ref="noteFormRef" :model="noteFormData" :rules="noteFormRules" label-placement="top">
        <n-form-item label="类型" path="type">
          <n-select v-model:value="noteFormData.type" :options="typeOptions" />
        </n-form-item>
        <n-form-item label="标题" path="title">
          <n-input v-model:value="noteFormData.title" placeholder="简短描述" />
        </n-form-item>
        <n-form-item label="关联卷（可选）" path="volume_id">
          <n-select
            v-model:value="noteFormData.volume_id"
            :options="volumeOptions"
            placeholder="选择卷（生成该卷章节时自动注入）"
            clearable
          />
        </n-form-item>
        <n-form-item v-if="noteFormData.type === 'chapter'" label="关联章节" path="chapter_number">
          <n-input-number v-model:value="noteFormData.chapter_number" :min="1" placeholder="章节号" style="width: 100%;" />
        </n-form-item>
        <n-form-item v-if="noteFormData.type === 'character_secret'" label="关联角色" path="character_id">
          <n-select v-model:value="noteFormData.character_id" :options="characterOptions" placeholder="选择角色" />
        </n-form-item>
        <n-form-item label="内容" path="content">
          <n-input
            v-model:value="noteFormData.content"
            type="textarea"
            :rows="6"
            placeholder="详细内容..."
          />
        </n-form-item>
        <n-form-item label="优先级" path="priority">
          <n-slider v-model:value="noteFormData.priority" :min="0" :max="10" :step="1" />
          <span class="ml-2 text-sm text-slate-500">{{ noteFormData.priority }}</span>
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showNoteModal = false">取消</n-button>
        <n-button type="primary" :loading="savingNote" @click="handleSaveNote">保存</n-button>
      </template>
    </n-modal>

    <!-- 添加/编辑状态弹窗 -->
    <n-modal v-model:show="showStateModal" preset="dialog" :title="editingState ? '编辑角色状态' : '新增角色状态'" style="width: 700px;">
      <n-form ref="stateFormRef" :model="stateFormData" :rules="stateFormRules" label-placement="top">
        <n-form-item label="选择角色" path="character_id">
          <n-select
            v-model:value="stateFormData.character_id"
            :options="characterOptions"
            :disabled="!!editingState"
            placeholder="选择角色"
          />
        </n-form-item>
        <n-form-item label="章节号" path="chapter_number">
          <n-input-number
            v-model:value="stateFormData.chapter_number"
            :min="1"
            :disabled="!!editingState"
            placeholder="该状态对应的章节"
            style="width: 100%;"
          />
        </n-form-item>

        <!-- 动态属性编辑 -->
        <div class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-medium text-slate-700">状态属性</label>
            <button
              type="button"
              class="text-sm text-indigo-600 hover:text-indigo-700"
              @click="addAttribute"
            >
              + 添加属性
            </button>
          </div>
          <div class="space-y-2">
            <div
              v-for="(attr, index) in stateAttributes"
              :key="index"
              class="flex items-center gap-2"
            >
              <n-input
                v-model:value="attr.key"
                placeholder="属性名（如：等级）"
                class="flex-1"
              />
              <n-input
                v-model:value="attr.value"
                placeholder="属性值（如：35）"
                class="flex-1"
              />
              <button
                type="button"
                class="p-1.5 text-gray-400 hover:text-red-500"
                @click="removeAttribute(index)"
              >
                <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                </svg>
              </button>
            </div>
          </div>
          <p v-if="!stateAttributes.length" class="text-sm text-slate-400 mt-2">
            点击"添加属性"来记录角色数值
          </p>
        </div>

        <n-form-item label="变更备注" path="change_note">
          <n-input
            v-model:value="stateFormData.change_note"
            type="textarea"
            :rows="2"
            placeholder="简要说明本次变化原因（如：击杀Boss升级）"
          />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showStateModal = false">取消</n-button>
        <n-button type="primary" :loading="savingState" @click="handleSaveState">保存</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { NModal, NForm, NFormItem, NInput, NInputNumber, NSelect, NButton, NSlider, useMessage, useDialog } from 'naive-ui'
import type { FormInst, FormRules, SelectOption } from 'naive-ui'
import { marked } from 'marked'
import {
  listNotes,
  createNote,
  updateNote,
  deleteNote,
  listStates,
  upsertState,
  updateState,
  deleteState,
  type AuthorNote,
  type AuthorNoteType,
  type CreateNoteRequest,
  type CharacterState,
  type UpsertStateRequest
} from '@/api/authorNotes'

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true
})

// 渲染 Markdown
function renderMarkdown(content: string): string {
  return marked.parse(content) as string
}

interface Attribute {
  key: string
  value: string
}

const props = defineProps<{
  projectId: string
  editable?: boolean
  characters?: { id: number; name: string }[]
  volumes?: { id: number; title: string; volume_number: number }[]
}>()

const emit = defineEmits<{
  (e: 'update'): void
}>()

const message = useMessage()
const dialog = useDialog()

// ==================== 通用状态 ====================
const activeTab = ref<'notes' | 'states'>('notes')

// ==================== 备忘录状态 ====================
const notes = ref<AuthorNote[]>([])
const loadingNotes = ref(false)
const savingNote = ref(false)
const showNoteModal = ref(false)
const editingNote = ref<AuthorNote | null>(null)
const activeNoteFilter = ref<string>('all')
const noteFormRef = ref<FormInst | null>(null)

const noteFormData = ref<CreateNoteRequest>({
  type: 'chapter',
  title: '',
  content: '',
  chapter_number: undefined,
  volume_id: undefined,
  character_id: undefined,
  priority: 0
})

const typeFilters = [
  { value: 'all', label: '全部' },
  { value: 'chapter', label: '章节备忘' },
  { value: 'character_secret', label: '角色秘密' },
  { value: 'style', label: '写作风格' },
  { value: 'todo', label: '待办事项' },
  { value: 'global', label: '全局备忘' },
  { value: 'plot_thread', label: '剧情线索' },
  { value: 'timeline', label: '时间线' },
  { value: 'item', label: '物品/道具' },
  { value: 'location', label: '地点场景' },
  { value: 'ability', label: '技能/能力' },
  { value: 'revision', label: '待修改' },
  { value: 'world_building', label: '世界观补充' }
]

const typeOptions: SelectOption[] = [
  { value: 'chapter', label: '章节备忘' },
  { value: 'character_secret', label: '角色秘密' },
  { value: 'style', label: '写作风格' },
  { value: 'todo', label: '待办事项' },
  { value: 'global', label: '全局备忘' },
  { value: 'plot_thread', label: '剧情线索' },
  { value: 'timeline', label: '时间线' },
  { value: 'item', label: '物品/道具' },
  { value: 'location', label: '地点场景' },
  { value: 'ability', label: '技能/能力' },
  { value: 'revision', label: '待修改' },
  { value: 'world_building', label: '世界观补充' }
]

const noteFormRules: FormRules = {
  type: { required: true, message: '请选择类型' },
  title: { required: true, message: '请输入标题', trigger: 'blur' },
  content: { required: true, message: '请输入内容', trigger: 'blur' }
}

// ==================== 角色状态 ====================
const states = ref<CharacterState[]>([])
const loadingStates = ref(false)
const savingState = ref(false)
const showStateModal = ref(false)
const editingState = ref<CharacterState | null>(null)
const selectedCharacterId = ref<number | null>(null)
const stateFormRef = ref<FormInst | null>(null)
const stateAttributes = ref<Attribute[]>([])

const stateFormData = ref<{
  character_id: number | null
  chapter_number: number | null
  change_note: string
}>({
  character_id: null,
  chapter_number: null,
  change_note: ''
})

const stateFormRules: FormRules = {
  character_id: { required: true, type: 'number', message: '请选择角色' },
  chapter_number: { required: true, type: 'number', message: '请输入章节号' }
}

// ==================== 计算属性 ====================
const characters = computed(() => props.characters || [])
const volumes = computed(() => props.volumes || [])

const characterOptions = computed<SelectOption[]>(() => {
  return characters.value.map(c => ({
    value: c.id,
    label: c.name
  }))
})

const volumeOptions = computed<SelectOption[]>(() => {
  return volumes.value.map(v => ({
    value: v.id,
    label: `第${v.volume_number}卷 - ${v.title}`
  }))
})

// 备忘录相关
const chapterNotes = computed(() => notes.value.filter(n => n.type === 'chapter'))
const secretNotes = computed(() => notes.value.filter(n => n.type === 'character_secret'))
const styleNotes = computed(() => notes.value.filter(n => n.type === 'style'))
const globalNotes = computed(() => notes.value.filter(n => n.type === 'global'))

const filteredNotes = computed(() => {
  if (activeNoteFilter.value === 'all') return notes.value
  return notes.value.filter(n => n.type === activeNoteFilter.value)
})

// 角色状态相关
const filteredStates = computed(() => {
  if (selectedCharacterId.value === null) return states.value
  return states.value.filter(s => Number(s.character_id) === selectedCharacterId.value)
})

// ==================== 辅助函数 ====================
function getCountByType(type: string): number {
  if (type === 'all') return notes.value.length
  return notes.value.filter(n => n.type === type).length
}

function getTypeIcon(type: AuthorNoteType): string {
  const icons: Record<AuthorNoteType, string> = {
    chapter: '📝',
    character_secret: '🔒',
    style: '✍️',
    global: '📌',
    todo: '☑️',
    plot_thread: '🧵',
    timeline: '⏰',
    item: '🎒',
    location: '🏠',
    ability: '⚡',
    revision: '🔧',
    world_building: '🌍'
  }
  return icons[type] || '📄'
}

function getTypeLabel(type: AuthorNoteType): string {
  const labels: Record<AuthorNoteType, string> = {
    chapter: '章节备忘',
    character_secret: '角色秘密',
    style: '写作风格',
    global: '全局备忘',
    todo: '待办事项',
    plot_thread: '剧情线索',
    timeline: '时间线',
    item: '物品/道具',
    location: '地点场景',
    ability: '技能/能力',
    revision: '待修改',
    world_building: '世界观补充'
  }
  return labels[type] || type
}

function getTypeBadgeClass(type: AuthorNoteType): string {
  const classes: Record<AuthorNoteType, string> = {
    chapter: 'bg-blue-100 text-blue-700',
    character_secret: 'bg-purple-100 text-purple-700',
    style: 'bg-amber-100 text-amber-700',
    global: 'bg-slate-100 text-slate-700',
    todo: 'bg-green-100 text-green-700',
    plot_thread: 'bg-pink-100 text-pink-700',
    timeline: 'bg-cyan-100 text-cyan-700',
    item: 'bg-orange-100 text-orange-700',
    location: 'bg-teal-100 text-teal-700',
    ability: 'bg-yellow-100 text-yellow-700',
    revision: 'bg-red-100 text-red-700',
    world_building: 'bg-indigo-100 text-indigo-700'
  }
  return classes[type] || 'bg-gray-100 text-gray-700'
}

function selectCharacter(id: number | null): void {
  selectedCharacterId.value = id
}

function isCharacterSelected(id: number): boolean {
  if (selectedCharacterId.value === null) return false
  return Number(selectedCharacterId.value) === Number(id)
}

function getStateCountByCharacter(characterId: number): number {
  return states.value.filter(s => Number(s.character_id) === Number(characterId)).length
}

function getCharacterName(characterId: number): string {
  const char = characters.value.find(c => Number(c.id) === Number(characterId))
  return char?.name || `角色#${characterId}`
}

function getVolumeName(volumeId: number): string {
  const vol = volumes.value.find(v => Number(v.id) === Number(volumeId))
  return vol ? `第${vol.volume_number}卷` : `卷#${volumeId}`
}

function formatValue(value: unknown): string {
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value)
  }
  return String(value)
}

// ==================== 加载数据 ====================
async function loadNotes() {
  loadingNotes.value = true
  try {
    const res = await listNotes(props.projectId, undefined, false)
    notes.value = res.notes
  } catch (e: any) {
    message.error(e.message || '加载备忘录失败')
  } finally {
    loadingNotes.value = false
  }
}

async function loadStates() {
  loadingStates.value = true
  try {
    const res = await listStates(props.projectId)
    states.value = res.states
  } catch (e: any) {
    message.error(e.message || '加载状态失败')
  } finally {
    loadingStates.value = false
  }
}

// ==================== 备忘录操作 ====================
function openAddNoteModal() {
  editingNote.value = null
  noteFormData.value = {
    type: 'chapter',
    title: '',
    content: '',
    chapter_number: undefined,
    volume_id: undefined,
    character_id: undefined,
    priority: 0
  }
  showNoteModal.value = true
}

function openEditNoteModal(note: AuthorNote) {
  editingNote.value = note
  noteFormData.value = {
    type: note.type,
    title: note.title,
    content: note.content,
    chapter_number: note.chapter_number ?? undefined,
    volume_id: note.volume_id ?? undefined,
    character_id: note.character_id ?? undefined,
    priority: note.priority
  }
  showNoteModal.value = true
}

async function handleSaveNote() {
  await noteFormRef.value?.validate()
  savingNote.value = true
  try {
    if (editingNote.value) {
      await updateNote(props.projectId, editingNote.value.id, {
        title: noteFormData.value.title,
        content: noteFormData.value.content,
        priority: noteFormData.value.priority,
        volume_id: noteFormData.value.volume_id ?? null,
        chapter_number: noteFormData.value.chapter_number ?? null
      })
      message.success('更新成功')
    } else {
      await createNote(props.projectId, noteFormData.value)
      message.success('创建成功')
    }
    showNoteModal.value = false
    await loadNotes()
    emit('update')
  } catch (e: any) {
    message.error(e.message || '保存失败')
  } finally {
    savingNote.value = false
  }
}

function confirmDeleteNote(note: AuthorNote) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除备忘"${note.title}"吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteNote(props.projectId, note.id)
        message.success('删除成功')
        await loadNotes()
        emit('update')
      } catch (e: any) {
        message.error(e.message || '删除失败')
      }
    }
  })
}

// ==================== 状态操作 ====================
function addAttribute() {
  stateAttributes.value.push({ key: '', value: '' })
}

function removeAttribute(index: number) {
  stateAttributes.value.splice(index, 1)
}

function openAddStateModal() {
  editingState.value = null
  stateFormData.value = {
    character_id: null,
    chapter_number: null,
    change_note: ''
  }
  stateAttributes.value = [
    { key: '等级', value: '' },
    { key: '生命值', value: '' },
    { key: '攻击力', value: '' }
  ]
  showStateModal.value = true
}

function openEditStateModal(state: CharacterState) {
  editingState.value = state
  stateFormData.value = {
    character_id: state.character_id,
    chapter_number: state.chapter_number,
    change_note: state.change_note || ''
  }
  stateAttributes.value = Object.entries(state.data || {}).map(([key, value]) => ({
    key,
    value: String(value)
  }))
  showStateModal.value = true
}

async function handleSaveState() {
  await stateFormRef.value?.validate()

  const data: Record<string, unknown> = {}
  for (const attr of stateAttributes.value) {
    if (attr.key.trim()) {
      const numValue = Number(attr.value)
      data[attr.key.trim()] = isNaN(numValue) ? attr.value : numValue
    }
  }

  savingState.value = true
  try {
    if (editingState.value) {
      await updateState(props.projectId, editingState.value.id, {
        data,
        change_note: stateFormData.value.change_note || undefined
      })
      message.success('更新成功')
    } else {
      const req: UpsertStateRequest = {
        character_id: stateFormData.value.character_id!,
        chapter_number: stateFormData.value.chapter_number!,
        data,
        change_note: stateFormData.value.change_note || undefined
      }
      await upsertState(props.projectId, req)
      message.success('创建成功')
    }
    showStateModal.value = false
    await loadStates()
    emit('update')
  } catch (e: any) {
    message.error(e.message || '保存失败')
  } finally {
    savingState.value = false
  }
}

function confirmDeleteState(state: CharacterState) {
  const charName = state.character_name || getCharacterName(state.character_id)
  dialog.warning({
    title: '确认删除',
    content: `确定要删除"${charName}"在第${state.chapter_number}章的状态记录吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteState(props.projectId, state.id)
        message.success('删除成功')
        await loadStates()
        emit('update')
      } catch (e: any) {
        message.error(e.message || '删除失败')
      }
    }
  })
}

// ==================== 生命周期 ====================
watch(() => props.projectId, () => {
  if (props.projectId) {
    loadNotes()
    loadStates()
  }
}, { immediate: true })

onMounted(() => {
  if (props.projectId) {
    loadNotes()
    loadStates()
  }
})
</script>
