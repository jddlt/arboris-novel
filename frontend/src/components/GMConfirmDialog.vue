<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
        @click.self="handleBackdropClick"
      >
        <Transition name="scale">
          <div
            v-if="visible"
            class="bg-white rounded-xl shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col overflow-hidden"
          >
            <!-- 头部 -->
            <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-indigo-50 to-purple-50">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center">
                  <svg class="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <h3 class="text-lg font-semibold text-gray-800">确认执行操作</h3>
                  <p class="text-sm text-gray-500">
                    已选择 {{ selectedCount }}/{{ actions.length }} 个操作
                  </p>
                </div>
              </div>

              <!-- 超时倒计时 -->
              <div v-if="remainingTime > 0" class="text-sm text-gray-500 flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {{ Math.ceil(remainingTime / 1000) }}s
              </div>
            </div>

            <!-- 操作列表 -->
            <div class="flex-1 overflow-auto p-4 space-y-2">
              <div
                v-for="action in actions"
                :key="action.action_id"
                class="group flex items-start gap-3 p-4 rounded-lg border-2 transition-all duration-200 cursor-pointer"
                :class="getActionClasses(action)"
                @click="toggleAction(action.action_id)"
              >
                <!-- 复选框 -->
                <div class="flex-shrink-0 mt-0.5">
                  <div
                    class="w-5 h-5 rounded border-2 flex items-center justify-center transition-colors"
                    :class="selectedActions.has(action.action_id)
                      ? 'bg-indigo-600 border-indigo-600'
                      : 'border-gray-300 group-hover:border-indigo-400'"
                  >
                    <svg
                      v-if="selectedActions.has(action.action_id)"
                      class="w-3 h-3 text-white"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                    </svg>
                  </div>
                </div>

                <!-- 内容 -->
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="font-medium text-gray-800">{{ getToolDisplayName(action.tool_name) }}</span>
                    <span
                      v-if="action.is_dangerous"
                      class="inline-flex items-center gap-1 text-xs font-medium text-red-600 bg-red-50 px-2 py-0.5 rounded-full"
                    >
                      <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                      </svg>
                      危险操作
                    </span>
                  </div>
                  <p class="text-sm text-gray-600 mt-1">{{ action.preview }}</p>
                </div>
              </div>

              <div v-if="actions.length === 0" class="text-center py-8 text-gray-500">
                没有待确认的操作
              </div>
            </div>

            <!-- 底部按钮 -->
            <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex items-center justify-between">
              <div class="flex items-center gap-4">
                <button
                  @click="selectAll"
                  class="text-sm text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
                >
                  全选
                </button>
                <button
                  @click="selectNone"
                  class="text-sm text-gray-500 hover:text-gray-700 font-medium transition-colors"
                >
                  取消全选
                </button>
              </div>

              <div class="flex items-center gap-3">
                <button
                  @click="handleCancel"
                  class="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg font-medium transition-colors"
                >
                  取消任务
                </button>
                <button
                  @click="handleConfirm"
                  class="px-5 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                  :disabled="selectedCount === 0"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                  </svg>
                  确认执行 ({{ selectedCount }})
                </button>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'

// ==================== 类型 ====================

interface ActionPreview {
  action_id: string
  tool_name: string
  params: Record<string, unknown>
  preview: string
  is_dangerous: boolean
}

// ==================== Props & Emits ====================

const props = defineProps<{
  visible: boolean
  actions: ActionPreview[]
  timeoutMs?: number
}>()

const emit = defineEmits<{
  confirm: [approved: string[], rejected: string[]]
  cancel: []
}>()

// ==================== 状态 ====================

const selectedActions = ref(new Set<string>())
const remainingTime = ref(0)
let timeoutTimer: number | null = null
let countdownTimer: number | null = null

// ==================== 计算属性 ====================

const selectedCount = computed(() => selectedActions.value.size)

// ==================== 方法 ====================

function getToolDisplayName(toolName: string): string {
  const nameMap: Record<string, string> = {
    add_character: '添加角色',
    update_character: '更新角色',
    delete_character: '删除角色',
    add_outline: '添加大纲',
    update_outline: '更新大纲',
    delete_outline: '删除大纲',
    add_volume: '添加卷',
    update_volume: '更新卷',
    delete_volume: '删除卷',
    add_relationship: '添加关系',
    update_relationship: '更新关系',
    delete_relationship: '删除关系',
    add_foreshadowing: '添加伏笔',
    update_foreshadowing: '更新伏笔',
    delete_foreshadowing: '删除伏笔',
    update_blueprint: '更新蓝图',
    update_chapter_content: '更新章节内容',
    clear_chapter_content: '清空章节内容',
    generate_chapter_content: '生成章节内容',
  }
  return nameMap[toolName] || toolName
}

function getActionClasses(action: ActionPreview) {
  const isSelected = selectedActions.value.has(action.action_id)

  if (action.is_dangerous) {
    return isSelected
      ? 'border-red-400 bg-red-50'
      : 'border-red-200 hover:border-red-300 bg-white'
  }

  return isSelected
    ? 'border-indigo-400 bg-indigo-50'
    : 'border-gray-200 hover:border-indigo-200 bg-white'
}

function toggleAction(actionId: string) {
  if (selectedActions.value.has(actionId)) {
    selectedActions.value.delete(actionId)
  } else {
    selectedActions.value.add(actionId)
  }
}

function selectAll() {
  selectedActions.value = new Set(props.actions.map((a) => a.action_id))
}

function selectNone() {
  selectedActions.value = new Set()
}

function handleConfirm() {
  const approved = [...selectedActions.value]
  const rejected = props.actions
    .map((a) => a.action_id)
    .filter((id) => !selectedActions.value.has(id))

  clearTimers()
  emit('confirm', approved, rejected)
}

function handleCancel() {
  clearTimers()
  emit('cancel')
}

function handleBackdropClick() {
  // 点击背景不关闭，需要明确选择
}

function clearTimers() {
  if (timeoutTimer) {
    clearTimeout(timeoutTimer)
    timeoutTimer = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

// ==================== Watch ====================

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      // 默认选中所有非危险操作
      selectedActions.value = new Set(
        props.actions.filter((a) => !a.is_dangerous).map((a) => a.action_id)
      )

      // 启动超时倒计时
      const timeout = props.timeoutMs || 60000
      remainingTime.value = timeout

      countdownTimer = window.setInterval(() => {
        remainingTime.value = Math.max(0, remainingTime.value - 1000)
      }, 1000)

      timeoutTimer = window.setTimeout(() => {
        // 超时自动取消
        emit('cancel')
      }, timeout)
    } else {
      clearTimers()
    }
  }
)

// ==================== 生命周期 ====================

onUnmounted(() => {
  clearTimers()
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.scale-enter-active,
.scale-leave-active {
  transition: all 0.2s ease;
}

.scale-enter-from,
.scale-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
