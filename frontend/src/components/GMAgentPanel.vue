<template>
  <!-- 主面板容器 - 不再使用 Teleport，直接作为 flex 子元素 -->
  <div class="flex flex-col h-full bg-white border-l border-gray-200 overflow-hidden">
    <!-- 头部 -->
    <div class="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white flex-shrink-0">
      <div class="flex items-center gap-2">
        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zm0 16a3 3 0 01-3-3h6a3 3 0 01-3 3z"/>
        </svg>
        <span class="font-semibold">AI 助手</span>
      </div>
      <div class="flex items-center gap-2">
        <!-- 联网搜索开关 -->
        <label class="flex items-center gap-1 text-sm cursor-pointer" title="启用联网搜索（仅 Gemini 模型支持）">
          <input
            type="checkbox"
            v-model="enableWebSearch"
            class="w-4 h-4 rounded border-white/50 text-indigo-600 focus:ring-indigo-500"
          />
          <span class="text-xs opacity-90">联网</span>
        </label>
        <!-- 历史对话按钮 -->
        <button
          @click="toggleHistoryPanel"
          class="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
          :class="showHistoryPanel ? 'bg-white/20' : ''"
          title="历史对话"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
        </button>
        <!-- 新建对话按钮 -->
        <button
          @click="startNewConversation"
          class="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
          title="新建对话"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
        </button>
        <!-- 关闭按钮 -->
        <button
          @click="$emit('close')"
          class="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 历史对话下拉面板 -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      leave-active-class="transition-all duration-150 ease-in"
      enter-from-class="opacity-0 -translate-y-2"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div v-if="showHistoryPanel" class="border-b border-gray-200 bg-gray-50 max-h-64 overflow-y-auto flex-shrink-0">
        <!-- 加载中 -->
        <div v-if="isLoadingHistory" class="flex items-center justify-center py-6">
          <div class="w-5 h-5 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
          <span class="ml-2 text-sm text-gray-500">加载中...</span>
        </div>

        <!-- 无历史记录 -->
        <div v-else-if="historyList.length === 0" class="py-6 text-center text-gray-500 text-sm">
          暂无历史对话
        </div>

        <!-- 历史列表 -->
        <div v-else class="divide-y divide-gray-200">
          <button
            v-for="conv in historyList"
            :key="conv.id"
            @click="selectConversation(conv)"
            class="w-full px-4 py-3 text-left hover:bg-indigo-50 transition-colors flex items-center justify-between group"
            :class="conversationId === conv.id ? 'bg-indigo-50' : ''"
          >
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-900 truncate">{{ conv.title }}</div>
              <div class="text-xs text-gray-500 mt-0.5">{{ conv.message_count }} 条消息</div>
            </div>
            <div class="flex-shrink-0 ml-3">
              <span class="text-xs text-gray-400">{{ formatTime(conv.updated_at) }}</span>
              <div v-if="conversationId === conv.id" class="mt-1">
                <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-indigo-100 text-indigo-700">当前</span>
              </div>
            </div>
          </button>
        </div>
      </div>
    </Transition>

    <!-- 消息列表 -->
    <div ref="messageContainer" class="flex-1 overflow-y-auto p-4 space-y-4">
      <!-- 欢迎消息 -->
      <div v-if="messages.length === 0" class="text-center text-gray-500 py-8">
        <svg class="w-12 h-12 mx-auto mb-4 text-gray-300" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zm0 16a3 3 0 01-3-3h6a3 3 0 01-3 3z"/>
        </svg>
        <p class="text-sm">你好！我是这本小说的 AI 助手。</p>
        <p class="text-xs mt-1">我可以帮你管理角色、调整大纲、查看和修改章节内容。</p>
      </div>

      <!-- 消息气泡 -->
      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="['flex', msg.role === 'user' ? 'justify-end' : 'justify-start']"
      >
        <div
          :class="[
            'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm',
            msg.role === 'user'
              ? 'bg-indigo-500 text-white rounded-br-md'
              : 'bg-gray-100 text-gray-800 rounded-bl-md'
          ]"
        >
          <!-- 消息内容（支持 Markdown，长文本截断） -->
          <div
            v-if="msg.role === 'user'"
            class="whitespace-pre-wrap break-words"
          >{{ isLongContent(msg.content) ? truncateContent(msg.content) : msg.content }}</div>
          <div
            v-else
            class="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-pre:my-2 prose-code:px-1 prose-code:py-0.5 prose-code:bg-gray-200 prose-code:rounded prose-code:text-xs"
            v-html="renderMarkdown(isLongContent(msg.content) ? truncateContent(msg.content) : msg.content)"
          ></div>
          <button
            v-if="isLongContent(msg.content)"
            @click="showFullContent(msg.content)"
            :class="[
              'mt-2 text-xs font-medium underline',
              msg.role === 'user' ? 'text-indigo-200 hover:text-white' : 'text-indigo-600 hover:text-indigo-800'
            ]"
          >
            查看全文（{{ msg.content.length }} 字）
          </button>

          <!-- 待执行操作 -->
          <div v-if="msg.actions && msg.actions.length > 0" class="mt-3 space-y-2">
            <div
              v-for="action in msg.actions"
              :key="action.action_id"
              class="bg-white/90 rounded-lg p-2.5 border border-gray-200"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="flex-1">
                  <span class="text-xs font-medium text-indigo-600">{{ getToolLabel(action.tool_name) }}</span>
                  <p class="text-xs text-gray-600 mt-0.5">{{ action.preview }}</p>
                </div>
                <div v-if="action.status === 'pending'" class="flex gap-1">
                  <button
                    @click="applyAction(action.action_id)"
                    :disabled="isApplying"
                    class="p-1 text-green-600 hover:bg-green-50 rounded transition-colors disabled:opacity-50"
                    title="应用"
                  >
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                    </svg>
                  </button>
                  <button
                    @click="discardAction(action.action_id)"
                    :disabled="isApplying"
                    class="p-1 text-red-600 hover:bg-red-50 rounded transition-colors disabled:opacity-50"
                    title="放弃"
                  >
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
                    </svg>
                  </button>
                </div>
                <span v-else :class="getStatusClass(action.status)" class="text-xs px-1.5 py-0.5 rounded">
                  {{ getStatusLabel(action.status) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 流式输出中 -->
      <div v-if="isStreaming && streamingContent" class="flex justify-start">
        <div class="max-w-[85%] rounded-2xl rounded-bl-md px-4 py-2.5 bg-gray-100 text-gray-800 text-sm">
          <div
            class="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-pre:my-2 prose-code:px-1 prose-code:py-0.5 prose-code:bg-gray-200 prose-code:rounded prose-code:text-xs"
            v-html="renderMarkdown(streamingContent)"
          ></div>
          <span class="animate-pulse text-gray-400">|</span>
        </div>
      </div>

      <!-- 加载中（等待回复或流式输出还没内容时） -->
      <div v-if="isLoading && !streamingContent" class="flex justify-start">
        <div class="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
          <div class="flex gap-1">
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- 批量操作栏 -->
    <div v-if="pendingActionsCount > 0" class="px-4 py-2 bg-amber-50 border-t border-amber-200 flex-shrink-0">
      <div class="flex items-center justify-between">
        <span class="text-sm text-amber-800">
          {{ pendingActionsCount }} 个待执行操作
        </span>
        <div class="flex gap-2">
          <button
            @click="applyAllPending"
            :disabled="isApplying"
            class="px-3 py-1 text-xs bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50"
          >
            全部应用
          </button>
          <button
            @click="discardAllPending"
            :disabled="isApplying"
            class="px-3 py-1 text-xs bg-gray-400 text-white rounded-lg hover:bg-gray-500 disabled:opacity-50"
          >
            全部放弃
          </button>
        </div>
      </div>
    </div>

    <!-- 输入框 -->
    <div class="p-3 border-t border-gray-200 flex-shrink-0">
      <div class="flex gap-2 items-start">
        <textarea
          v-model="inputMessage"
          @keydown.enter.exact.prevent="sendMessage"
          :disabled="isLoading"
          placeholder="输入消息..."
          rows="3"
          class="flex-1 px-3 py-2 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-100 text-sm"
        ></textarea>
        <button
          @click="sendMessage"
          :disabled="!inputMessage.trim() || isLoading"
          class="px-4 py-3 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z"/>
          </svg>
        </button>
      </div>
    </div>
  </div>

  <!-- 全文查看 Modal - 仍然使用 Teleport -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div v-if="fullContentModal.show" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4" @click.self="closeFullContent">
        <div class="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] flex flex-col">
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <h3 class="text-lg font-semibold text-gray-900">完整内容</h3>
            <button
              @click="closeFullContent"
              class="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <div class="flex-1 overflow-y-auto px-6 py-4">
            <div
              class="prose prose-sm max-w-none text-gray-700 leading-relaxed"
              v-html="renderMarkdown(fullContentModal.content)"
            ></div>
          </div>
          <div class="px-6 py-3 border-t border-gray-200 bg-gray-50 rounded-b-2xl">
            <p class="text-xs text-gray-500 text-center">共 {{ fullContentModal.content.length }} 字</p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { marked } from 'marked'
import {
  streamChatWithGM,
  applyActions,
  discardActions,
  getConversations,
  getConversationDetail,
  type GMPendingAction,
  type ConversationMessage,
  type ConversationSummary,
} from '@/api/gm'

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

// 渲染 Markdown
function renderMarkdown(content: string): string {
  try {
    return marked.parse(content) as string
  } catch {
    return content
  }
}

const props = defineProps<{
  projectId: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'refresh'): void
}>()

// localStorage 键名
const STORAGE_KEY_PREFIX = 'gm_agent_chat_'
const getStorageKey = () => `${STORAGE_KEY_PREFIX}${props.projectId}`

// 状态
const messages = ref<(ConversationMessage & { actions?: GMPendingAction[] })[]>([])
const inputMessage = ref('')
const isLoading = ref(false)
const isStreaming = ref(false)
const streamingContent = ref('')
const isApplying = ref(false)
const conversationId = ref<string | null>(null)
const enableWebSearch = ref(false)
const messageContainer = ref<HTMLElement | null>(null)

// 历史对话列表状态
const showHistoryPanel = ref(false)
const historyList = ref<ConversationSummary[]>([])
const isLoadingHistory = ref(false)

// 全文查看 Modal 状态
const fullContentModal = ref<{ show: boolean; content: string }>({
  show: false,
  content: '',
})

// 长文本阈值（字符数）
const LONG_CONTENT_THRESHOLD = 500

// 保存对话到 localStorage
function saveToLocalStorage() {
  try {
    const data = {
      messages: messages.value,
      conversationId: conversationId.value,
      enableWebSearch: enableWebSearch.value,
      timestamp: Date.now(),
    }
    localStorage.setItem(getStorageKey(), JSON.stringify(data))
  } catch (error) {
    console.error('保存对话失败:', error)
  }
}

// 从 localStorage 恢复对话
function loadFromLocalStorage() {
  try {
    const stored = localStorage.getItem(getStorageKey())
    if (stored) {
      const data = JSON.parse(stored)
      // 检查数据是否过期（7天）
      const maxAge = 7 * 24 * 60 * 60 * 1000
      if (Date.now() - data.timestamp < maxAge) {
        messages.value = data.messages || []
        conversationId.value = data.conversationId || null
        enableWebSearch.value = data.enableWebSearch || false
        scrollToBottom()
      } else {
        // 数据过期，清除
        localStorage.removeItem(getStorageKey())
      }
    }
  } catch (error) {
    console.error('恢复对话失败:', error)
  }
}

// 判断是否为长文本
function isLongContent(content: string): boolean {
  return content.length > LONG_CONTENT_THRESHOLD
}

// 截断内容
function truncateContent(content: string): string {
  if (content.length <= LONG_CONTENT_THRESHOLD) return content
  return content.slice(0, LONG_CONTENT_THRESHOLD) + '...'
}

// 显示完整内容
function showFullContent(content: string) {
  fullContentModal.value = { show: true, content }
}

// 关闭全文查看
function closeFullContent() {
  fullContentModal.value = { show: false, content: '' }
}

// 工具标签映射
const toolLabels: Record<string, string> = {
  update_blueprint: '修改设定',
  add_character: '添加角色',
  update_character: '修改角色',
  delete_character: '删除角色',
  add_relationship: '添加关系',
  update_relationship: '修改关系',
  delete_relationship: '删除关系',
  add_outline: '添加大纲',
  update_outline: '修改大纲',
  delete_outline: '删除大纲',
  reorder_outlines: '调整顺序',
  search_content: '搜索内容',
  get_chapter_content: '获取章节',
  update_chapter_content: '修改章节',
}

// 计算待执行操作数量
const pendingActionsCount = computed(() => {
  let count = 0
  for (const msg of messages.value) {
    if (msg.actions) {
      count += msg.actions.filter(a => a.status === 'pending').length
    }
  }
  return count
})

// 获取工具标签
function getToolLabel(toolName: string): string {
  return toolLabels[toolName] || toolName
}

// 获取状态标签
function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    applied: '已应用',
    discarded: '已放弃',
    failed: '失败',
    pending: '待执行',
  }
  return labels[status] || status
}

// 获取状态样式
function getStatusClass(status: string): string {
  const classes: Record<string, string> = {
    applied: 'bg-green-100 text-green-700',
    discarded: 'bg-gray-100 text-gray-500',
    failed: 'bg-red-100 text-red-700',
  }
  return classes[status] || 'bg-gray-100 text-gray-600'
}

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (messageContainer.value) {
      messageContainer.value.scrollTop = messageContainer.value.scrollHeight
    }
  })
}

// 发送消息
async function sendMessage() {
  const content = inputMessage.value.trim()
  if (!content || isLoading.value) return

  inputMessage.value = ''
  isLoading.value = true
  isStreaming.value = true
  streamingContent.value = ''

  // 添加用户消息
  messages.value.push({ role: 'user', content })
  scrollToBottom()

  try {
    let pendingActions: GMPendingAction[] = []
    let finalContent = ''

    for await (const event of streamChatWithGM(props.projectId, content, {
      conversationId: conversationId.value || undefined,
      enableWebSearch: enableWebSearch.value,
    })) {
      if (event.type === 'start') {
        conversationId.value = event.conversation_id
      } else if (event.type === 'content') {
        streamingContent.value += event.content
        scrollToBottom()
      } else if (event.type === 'pending_actions') {
        pendingActions = event.actions
      } else if (event.type === 'done') {
        finalContent = event.message
      } else if (event.type === 'error') {
        throw new Error(event.error)
      }
    }

    isStreaming.value = false

    // 添加助手消息
    messages.value.push({
      role: 'assistant',
      content: finalContent || streamingContent.value,
      actions: pendingActions,
    })
    scrollToBottom()
  } catch (error) {
    isStreaming.value = false
    const errorMessage = error instanceof Error ? error.message : '发送失败'
    messages.value.push({
      role: 'assistant',
      content: `抱歉，发生了错误：${errorMessage}`,
    })
    scrollToBottom()
  } finally {
    isLoading.value = false
    streamingContent.value = ''
  }
}

// 应用单个操作
async function applyAction(actionId: string) {
  if (isApplying.value) return
  isApplying.value = true

  try {
    const result = await applyActions(props.projectId, [actionId])

    // 更新操作状态
    for (const msg of messages.value) {
      if (msg.actions) {
        for (const action of msg.actions) {
          if (action.action_id === actionId) {
            const res = result.results.find(r => r.action_id === actionId)
            action.status = res?.success ? 'applied' : 'failed'
          }
        }
      }
    }

    // 通知刷新数据
    emit('refresh')
  } catch (error) {
    console.error('应用操作失败:', error)
  } finally {
    isApplying.value = false
  }
}

// 放弃单个操作
async function discardAction(actionId: string) {
  if (isApplying.value) return
  isApplying.value = true

  try {
    await discardActions(props.projectId, [actionId])

    // 更新操作状态
    for (const msg of messages.value) {
      if (msg.actions) {
        for (const action of msg.actions) {
          if (action.action_id === actionId) {
            action.status = 'discarded'
          }
        }
      }
    }
  } catch (error) {
    console.error('放弃操作失败:', error)
  } finally {
    isApplying.value = false
  }
}

// 应用所有待执行操作
async function applyAllPending() {
  const pendingIds: string[] = []
  for (const msg of messages.value) {
    if (msg.actions) {
      for (const action of msg.actions) {
        if (action.status === 'pending') {
          pendingIds.push(action.action_id)
        }
      }
    }
  }

  if (pendingIds.length === 0) return

  isApplying.value = true
  try {
    const result = await applyActions(props.projectId, pendingIds)

    // 更新所有操作状态
    for (const msg of messages.value) {
      if (msg.actions) {
        for (const action of msg.actions) {
          const res = result.results.find(r => r.action_id === action.action_id)
          if (res) {
            action.status = res.success ? 'applied' : 'failed'
          }
        }
      }
    }

    emit('refresh')
  } catch (error) {
    console.error('批量应用失败:', error)
  } finally {
    isApplying.value = false
  }
}

// 放弃所有待执行操作
async function discardAllPending() {
  const pendingIds: string[] = []
  for (const msg of messages.value) {
    if (msg.actions) {
      for (const action of msg.actions) {
        if (action.status === 'pending') {
          pendingIds.push(action.action_id)
        }
      }
    }
  }

  if (pendingIds.length === 0) return

  isApplying.value = true
  try {
    await discardActions(props.projectId, pendingIds)

    for (const msg of messages.value) {
      if (msg.actions) {
        for (const action of msg.actions) {
          if (action.status === 'pending') {
            action.status = 'discarded'
          }
        }
      }
    }
  } catch (error) {
    console.error('批量放弃失败:', error)
  } finally {
    isApplying.value = false
  }
}

// 新建对话
function startNewConversation() {
  messages.value = []
  conversationId.value = null
  streamingContent.value = ''
  showHistoryPanel.value = false
  // 清除 localStorage 中的对话
  localStorage.removeItem(getStorageKey())
}

// 加载历史对话列表
async function loadHistoryList() {
  if (isLoadingHistory.value) return
  isLoadingHistory.value = true
  try {
    historyList.value = await getConversations(props.projectId)
  } catch (error) {
    console.error('加载历史对话失败:', error)
  } finally {
    isLoadingHistory.value = false
  }
}

// 切换历史面板显示
async function toggleHistoryPanel() {
  showHistoryPanel.value = !showHistoryPanel.value
  if (showHistoryPanel.value) {
    await loadHistoryList()
  }
}

// 选择历史对话
async function selectConversation(conv: ConversationSummary) {
  try {
    isLoading.value = true
    const detail = await getConversationDetail(props.projectId, conv.id)
    messages.value = detail.messages.map(msg => ({
      ...msg,
      actions: msg.actions?.map(a => ({
        action_id: a.action_id,
        tool_name: a.tool_name || '',
        params: {},
        preview: a.preview || '',
        status: a.status as GMPendingAction['status'],
      })),
    }))
    conversationId.value = conv.id
    showHistoryPanel.value = false
    saveToLocalStorage()
    scrollToBottom()
  } catch (error) {
    console.error('加载对话详情失败:', error)
  } finally {
    isLoading.value = false
  }
}

// 格式化时间
function formatTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (days === 1) {
    return '昨天'
  } else if (days < 7) {
    return `${days}天前`
  } else {
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  }
}

// 组件挂载时恢复对话
onMounted(() => {
  loadFromLocalStorage()
})

// 监听消息变化，自动滚动并保存
watch(messages, () => {
  scrollToBottom()
  saveToLocalStorage()
}, { deep: true })

// 监听 conversationId 变化，保存
watch(conversationId, saveToLocalStorage)
</script>
