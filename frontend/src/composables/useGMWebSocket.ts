/**
 * GM Agent WebSocket Composable
 * 提供基于 WebSocket 的 GM Agent 对话功能，支持同步确认
 */

import { ref, computed, onUnmounted, shallowRef } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { API_BASE_URL } from '@/api/novel'

// ==================== 类型定义 ====================

/** 待确认操作 */
export interface ActionPreview {
  action_id: string
  tool_name: string
  params: Record<string, unknown>
  preview: string
  is_dangerous: boolean
  status: 'pending' | 'approved' | 'rejected' | 'applied' | 'failed'
}

/** 工具执行记录 */
export interface ToolExecution {
  tool_name: string
  params: Record<string, unknown>
  status: 'executing' | 'success' | 'failed'
  message?: string
  preview?: string
}

/** 对话消息 */
export interface GMMessage {
  role: 'user' | 'assistant'
  content: string
  tools?: ToolExecution[]
  actions?: ActionPreview[]  // 待确认操作
  timestamp?: number
}

/** 确认状态 */
export interface ConfirmState {
  actions: ActionPreview[]
  timeoutMs: number
  resolver: ((response: { approved: string[]; rejected: string[] }) => void) | null
}

/** WebSocket 连接状态 */
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

/** 执行统计 */
export interface ExecutionStats {
  success: number
  failed: number
  skipped: number
}

// ==================== Composable ====================

export function useGMWebSocket(projectId: string) {
  // WebSocket 连接
  const ws = shallowRef<WebSocket | null>(null)
  const connectionStatus = ref<ConnectionStatus>('disconnected')
  const lastError = ref<string | null>(null)

  // 对话状态
  const conversationId = ref<string | null>(null)
  const messages = ref<GMMessage[]>([])
  const isLoading = ref(false)
  const streamingContent = ref('')

  // 工具执行状态
  const executingTools = ref<ToolExecution[]>([])

  // 确认状态
  const pendingConfirm = ref<ConfirmState | null>(null)

  // 本轮对话产生的 actions（用于区分跨轮次的 pendingConfirm）
  const currentRoundActions = ref<ActionPreview[]>([])

  // 执行统计
  const executionStats = ref<ExecutionStats | null>(null)

  // 计算属性
  const isConnected = computed(() => connectionStatus.value === 'connected')
  const hasUnconfirmedActions = computed(() => pendingConfirm.value !== null)

  // ==================== WebSocket 连接管理 ====================

  function connect() {
    if (ws.value?.readyState === WebSocket.OPEN) {
      return
    }

    connectionStatus.value = 'connecting'
    lastError.value = null

    // 构建 WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const baseUrl = API_BASE_URL.replace(/^https?:/, protocol)
    const url = `${baseUrl}/api/novels/${projectId}/gm/ws`

    // 添加认证 token
    const authStore = useAuthStore()
    const tokenParam = authStore.token ? `?token=${authStore.token}` : ''

    ws.value = new WebSocket(url + tokenParam)

    ws.value.onopen = () => {
      console.log('[GM WebSocket] 连接已建立')
      connectionStatus.value = 'connected'
    }

    ws.value.onclose = (event) => {
      console.log('[GM WebSocket] 连接已关闭', event.code, event.reason)
      connectionStatus.value = 'disconnected'
      ws.value = null

      // 如果有未完成的确认，取消它
      if (pendingConfirm.value?.resolver) {
        pendingConfirm.value.resolver({ approved: [], rejected: [] })
        pendingConfirm.value = null
      }
    }

    ws.value.onerror = (error) => {
      console.error('[GM WebSocket] 连接错误', error)
      connectionStatus.value = 'error'
      lastError.value = '连接失败'
    }

    ws.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleMessage(data)
      } catch (e) {
        console.error('[GM WebSocket] 消息解析失败', e)
      }
    }
  }

  function disconnect() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    connectionStatus.value = 'disconnected'
  }

  function reconnect() {
    disconnect()
    setTimeout(connect, 1000)
  }

  // ==================== 消息处理 ====================

  function handleMessage(data: Record<string, unknown>) {
    const type = data.type as string

    switch (type) {
      case 'connected':
        console.log('[GM WebSocket] 服务端确认连接', data.project_id)
        if (data.conversation_id) {
          conversationId.value = data.conversation_id as string
        }
        break

      case 'content':
        // 流式内容
        streamingContent.value += data.content as string
        break

      case 'tool_call':
        // AI 发起工具调用（流式，立即显示）
        {
          const toolName = data.tool_name as string
          const params = data.params as Record<string, unknown>
          // 立即添加到执行中工具列表，状态为 executing
          executingTools.value.push({
            tool_name: toolName,
            params: params,
            status: 'executing',
            preview: undefined,
          })
          console.log('[GM WebSocket] 工具调用通知:', toolName)
        }
        break

      case 'tool_executing':
        // 工具开始执行（可能已经通过 tool_call 添加过了）
        {
          const toolName = data.tool_name as string
          const params = data.params as Record<string, unknown>
          const preview = data.preview as string | undefined
          // 检查是否已经存在（通过 tool_call 添加的）
          const existingTool = executingTools.value.find(
            (t) => t.tool_name === toolName && t.status === 'executing'
          )
          if (existingTool) {
            // 更新 preview
            existingTool.preview = preview
          } else {
            // 新添加
            executingTools.value.push({
              tool_name: toolName,
              params: params,
              status: 'executing',
              preview: preview,
            })
          }
        }
        break

      case 'tool_result':
        // 工具执行完成
        {
          const toolName = data.tool_name as string
          const tool = executingTools.value.find(
            (t) => t.tool_name === toolName && t.status === 'executing'
          )
          if (tool) {
            tool.status = (data.success as boolean) ? 'success' : 'failed'
            tool.message = data.message as string
          }
        }
        break

      case 'confirm_actions':
        // 请求用户确认 - 只存储待确认操作，不再阻塞等待
        // 用户通过 /apply API 确认执行，刷新后操作仍然存在
        {
          const rawActions = data.actions as Array<Omit<ActionPreview, 'status'>>

          // 为每个操作添加 pending 状态
          const actionsWithStatus: ActionPreview[] = rawActions.map(a => ({
            ...a,
            status: 'pending' as const,
          }))

          // 记录本轮产生的 actions
          currentRoundActions.value = actionsWithStatus

          // 存储待确认操作（用于 UI 显示）
          pendingConfirm.value = {
            actions: actionsWithStatus,
            timeoutMs: 0, // 无超时限制
            resolver: null, // 不再使用 Promise 机制
          }
        }
        break

      case 'tool_executed':
        // 修改工具执行完成
        console.log('[GM WebSocket] 工具已执行', data.tool_name, data.success)
        break

      case 'done':
        // 任务完成
        isLoading.value = false
        conversationId.value = data.conversation_id as string

        // 保存消息（包含工具执行记录和本轮产生的待确认操作）
        // 注意：使用 currentRoundActions 而不是 pendingConfirm，避免跨轮次污染
        if (streamingContent.value || currentRoundActions.value.length) {
          messages.value.push({
            role: 'assistant',
            content: streamingContent.value,
            tools: [...executingTools.value],
            actions: currentRoundActions.value.length > 0 ? [...currentRoundActions.value] : undefined,
            timestamp: Date.now(),
          })
        }

        // 保存执行统计
        if (data.tool_execution_summary) {
          executionStats.value = data.tool_execution_summary as ExecutionStats
        }

        // 重置本轮状态
        streamingContent.value = ''
        executingTools.value = []
        currentRoundActions.value = []
        break

      case 'error':
        // 错误
        lastError.value = data.error as string
        if (!(data.recoverable as boolean)) {
          isLoading.value = false
        }
        break

      case 'pong':
        // 心跳响应
        break

      default:
        console.warn('[GM WebSocket] 未知消息类型', type)
    }
  }

  // ==================== 发送消息 ====================

  function sendMessage(data: Record<string, unknown>) {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      console.error('[GM WebSocket] 未连接，无法发送消息')
      return false
    }

    ws.value.send(JSON.stringify(data))
    return true
  }

  /**
   * 发送用户消息
   */
  function sendUserMessage(
    message: string,
    options?: {
      images?: { base64: string; mime_type: string }[]
      enableWebSearch?: boolean
    }
  ) {
    if (!message.trim()) return

    // 添加用户消息到列表
    messages.value.push({
      role: 'user',
      content: message,
      timestamp: Date.now(),
    })

    // 重置状态
    isLoading.value = true
    streamingContent.value = ''
    executingTools.value = []
    currentRoundActions.value = []  // 清空本轮 actions
    lastError.value = null
    executionStats.value = null

    // 发送消息
    sendMessage({
      type: 'user_message',
      message,
      conversation_id: conversationId.value,
      images: options?.images,
      enable_web_search: options?.enableWebSearch,
    })
  }

  /**
   * 确认操作 - 只更新本地状态，实际执行通过 /apply API
   */
  function confirmActions(approved: string[], rejected: string[] = []) {
    // 更新消息中的操作状态
    updateActionStatuses(approved, rejected)
    // 更新 pendingConfirm 中的状态
    if (pendingConfirm.value) {
      for (const action of pendingConfirm.value.actions) {
        if (approved.includes(action.action_id)) {
          action.status = 'approved'
        } else if (rejected.includes(action.action_id)) {
          action.status = 'rejected'
        }
      }
    }
  }

  /**
   * 确认单个操作 - 只更新本地状态
   */
  function approveAction(actionId: string) {
    // 更新 pendingConfirm 中的状态
    if (pendingConfirm.value) {
      const action = pendingConfirm.value.actions.find(a => a.action_id === actionId)
      if (action) {
        action.status = 'approved'
      }
    }

    // 更新消息中的状态
    updateActionStatusInMessages(actionId, 'approved')
  }

  /**
   * 拒绝单个操作 - 只更新本地状态
   */
  function rejectAction(actionId: string) {
    // 更新 pendingConfirm 中的状态
    if (pendingConfirm.value) {
      const action = pendingConfirm.value.actions.find(a => a.action_id === actionId)
      if (action) {
        action.status = 'rejected'
      }
    }

    // 更新消息中的状态
    updateActionStatusInMessages(actionId, 'rejected')
  }

  /**
   * 更新消息中单个操作的状态
   */
  function updateActionStatusInMessages(actionId: string, status: ActionPreview['status']) {
    for (const msg of messages.value) {
      if (msg.actions) {
        const action = msg.actions.find(a => a.action_id === actionId)
        if (action) {
          action.status = status
          break
        }
      }
    }
  }

  /**
   * 批量更新操作状态
   */
  function updateActionStatuses(approved: string[], rejected: string[]) {
    for (const msg of messages.value) {
      if (msg.actions) {
        for (const action of msg.actions) {
          if (approved.includes(action.action_id)) {
            action.status = 'approved'
          } else if (rejected.includes(action.action_id)) {
            action.status = 'rejected'
          }
        }
      }
    }
  }

  /**
   * 清除待确认状态
   */
  function clearPendingConfirm() {
    pendingConfirm.value = null
  }

  /**
   * 更新操作状态为已应用
   */
  function markActionsApplied(actionIds: string[]) {
    // 更新消息中的状态
    for (const msg of messages.value) {
      if (msg.actions) {
        for (const action of msg.actions) {
          if (actionIds.includes(action.action_id)) {
            action.status = 'applied'
          }
        }
      }
    }
    // 更新 pendingConfirm 中的状态
    if (pendingConfirm.value) {
      for (const action of pendingConfirm.value.actions) {
        if (actionIds.includes(action.action_id)) {
          action.status = 'applied'
        }
      }
    }
  }

  /**
   * 更新操作状态为失败
   */
  function markActionsFailed(actionIds: string[]) {
    // 更新消息中的状态
    for (const msg of messages.value) {
      if (msg.actions) {
        for (const action of msg.actions) {
          if (actionIds.includes(action.action_id)) {
            action.status = 'failed'
          }
        }
      }
    }
    // 更新 pendingConfirm 中的状态
    if (pendingConfirm.value) {
      for (const action of pendingConfirm.value.actions) {
        if (actionIds.includes(action.action_id)) {
          action.status = 'failed'
        }
      }
    }
  }

  /**
   * 确认所有操作 - 只更新本地状态
   */
  function confirmAll() {
    if (pendingConfirm.value) {
      const allIds = pendingConfirm.value.actions.map((a) => a.action_id)
      confirmActions(allIds, [])
    }
  }

  /**
   * 拒绝所有操作
   */
  function rejectAll() {
    if (pendingConfirm.value) {
      const allIds = pendingConfirm.value.actions.map((a) => a.action_id)
      confirmActions([], allIds)
    }
  }

  /**
   * 取消当前任务
   */
  function cancelTask() {
    if (pendingConfirm.value?.resolver) {
      pendingConfirm.value.resolver({ approved: [], rejected: [] })
      pendingConfirm.value = null
    }
    sendMessage({ type: 'cancel' })
    isLoading.value = false
  }

  /**
   * 清空对话
   */
  function clearConversation() {
    messages.value = []
    conversationId.value = null
    streamingContent.value = ''
    executingTools.value = []
    lastError.value = null
    executionStats.value = null
  }

  /**
   * 加载历史对话
   */
  function loadMessages(history: GMMessage[], convId?: string) {
    messages.value = history
    if (convId) {
      conversationId.value = convId
    }
  }

  // ==================== 生命周期 ====================

  onUnmounted(() => {
    disconnect()
  })

  // ==================== 返回值 ====================

  return {
    // 状态
    connectionStatus,
    isConnected,
    lastError,
    conversationId,
    messages,
    isLoading,
    streamingContent,
    executingTools,
    pendingConfirm,
    hasUnconfirmedActions,
    executionStats,

    // 方法
    connect,
    disconnect,
    reconnect,
    sendUserMessage,
    confirmActions,
    approveAction,
    rejectAction,
    confirmAll,
    rejectAll,
    cancelTask,
    clearConversation,
    loadMessages,
    clearPendingConfirm,
    markActionsApplied,
    markActionsFailed,
  }
}
