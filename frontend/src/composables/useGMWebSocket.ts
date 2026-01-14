/**
 * GM Agent WebSocket Composable
 * 提供基于 WebSocket 的 GM Agent 对话功能，支持同步确认
 *
 * 重构说明：
 * 1. 统一 ToolExecution 类型，用 requiresConfirmation 区分只读和修改工具
 * 2. 消除重复的状态更新逻辑，使用通用 updateToolStatus 函数
 * 3. 用 call_id 匹配工具，而不是 tool_name（修复重复工具调用的 bug）
 */

import { ref, computed, onUnmounted, shallowRef } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { API_BASE_URL } from '@/api/novel'

// ==================== 类型定义 ====================

/** 工具执行状态 */
export type ToolStatus =
  | 'pending'      // 待确认（修改工具）
  | 'approved'     // 已批准（修改工具）
  | 'rejected'     // 已拒绝（修改工具）
  | 'executing'    // 执行中
  | 'applied'      // 执行成功（已应用）
  | 'success'      // 执行成功（兼容旧数据）
  | 'failed'       // 执行失败

/** 统一的工具执行记录 */
export interface ToolExecution {
  /** 唯一标识（只读工具用 call_id，修改工具用 action_id） */
  id: string
  /** @deprecated 使用 id 代替，保留用于向后兼容 */
  action_id?: string
  tool_name: string
  params: Record<string, unknown>
  status: ToolStatus
  /** 是否需要用户确认（true = 修改工具，false = 只读工具） */
  requires_confirmation: boolean
  /** 操作预览文本（人类可读） */
  preview?: string
  /** 执行结果消息 */
  message?: string
  /** 是否为危险操作 */
  is_dangerous?: boolean
}

/** 对话消息 */
export interface GMMessage {
  role: 'user' | 'assistant'
  content: string
  /** 本消息关联的工具执行记录（统一存储只读和修改工具） */
  tools?: ToolExecution[]
  /** 待确认/已确认的操作（仅包含 requires_confirmation=true 的工具，兼容历史消息格式） */
  actions?: ToolExecution[]
  /** 用户发送的图片 */
  images?: { base64: string; mime_type: string }[]
  timestamp?: number
}

/** 确认状态 */
export interface ConfirmState {
  /** 待确认的工具列表（仅包含 requires_confirmation=true 的工具） */
  tools: ToolExecution[]
  /** @deprecated 使用 tools 代替 */
  actions: ToolExecution[]
  /** 是否需要确认后继续 Agent 循环 */
  awaitingConfirmation: boolean
}

/** WebSocket 连接状态 */
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

/** 执行统计 */
export interface ExecutionStats {
  success: number
  failed: number
  skipped: number
}

// ==================== 兼容类型（向后兼容，逐步废弃） ====================

/** @deprecated 使用 ToolExecution 代替 */
export type ActionPreview = ToolExecution

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

  // 本轮工具执行状态（包含只读和修改工具）
  const currentRoundTools = ref<ToolExecution[]>([])

  // 确认状态
  const pendingConfirm = ref<ConfirmState | null>(null)

  // 执行统计
  const executionStats = ref<ExecutionStats | null>(null)

  // 计算属性
  const isConnected = computed(() => connectionStatus.value === 'connected')
  const hasUnconfirmedActions = computed(() => pendingConfirm.value !== null)

  // 兼容属性：executingTools 映射到 currentRoundTools
  const executingTools = computed(() => currentRoundTools.value)

  // 兼容属性：currentRoundActions 映射到需要确认的工具
  const currentRoundActions = computed(() =>
    currentRoundTools.value.filter(t => t.requires_confirmation)
  )

  // ==================== 核心工具函数 ====================

  /**
   * 更新工具状态（统一入口，消除重复逻辑）
   */
  function updateToolStatus(toolId: string, status: ToolStatus, message?: string) {
    // 更新当前轮次
    const tool = currentRoundTools.value.find(t => t.id === toolId)
    if (tool) {
      tool.status = status
      if (message !== undefined) tool.message = message
    }

    // 更新 pendingConfirm
    if (pendingConfirm.value) {
      const pendingTool = pendingConfirm.value.tools.find(t => t.id === toolId)
      if (pendingTool) {
        pendingTool.status = status
        if (message !== undefined) pendingTool.message = message
      }
    }

    // 更新历史消息
    for (const msg of messages.value) {
      // 在 tools 中查找
      if (msg.tools) {
        const historyTool = msg.tools.find(t => t.id === toolId)
        if (historyTool) {
          historyTool.status = status
          if (message !== undefined) historyTool.message = message
        }
      }
      // 在 actions 中查找（兼容历史消息格式）
      if (msg.actions) {
        const historyAction = msg.actions.find(t => t.id === toolId || t.action_id === toolId)
        if (historyAction) {
          historyAction.status = status
          if (message !== undefined) historyAction.message = message
        }
      }
    }
  }

  /**
   * 批量更新工具状态
   */
  function updateToolStatuses(
    approvedIds: string[],
    rejectedIds: string[],
    targetStatus?: { approved: ToolStatus; rejected: ToolStatus }
  ) {
    const approvedStatus = targetStatus?.approved ?? 'approved'
    const rejectedStatus = targetStatus?.rejected ?? 'rejected'

    for (const id of approvedIds) {
      updateToolStatus(id, approvedStatus)
    }
    for (const id of rejectedIds) {
      updateToolStatus(id, rejectedStatus)
    }
  }

  /**
   * 通过 call_id 或 tool_name 查找工具（优先 call_id）
   */
  function findTool(callId?: string, toolName?: string): ToolExecution | undefined {
    if (callId) {
      return currentRoundTools.value.find(t => t.id === callId)
    }
    if (toolName) {
      // 回退到 tool_name 匹配（兼容旧逻辑，但优先匹配 executing 状态的）
      return currentRoundTools.value.find(
        t => t.tool_name === toolName && t.status === 'executing'
      )
    }
    return undefined
  }

  // ==================== WebSocket 连接管理 ====================

  // 重连相关状态
  let reconnectAttempts = 0
  const MAX_RECONNECT_ATTEMPTS = 5
  const RECONNECT_DELAY_BASE = 1000 // 基础延迟 1 秒
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect() {
    if (ws.value?.readyState === WebSocket.OPEN) {
      return
    }

    // 清除之前的重连定时器
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    connectionStatus.value = 'connecting'
    lastError.value = null

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const baseUrl = API_BASE_URL.replace(/^https?:/, protocol)
    const url = `${baseUrl}/api/novels/${projectId}/gm/ws`

    const authStore = useAuthStore()
    const tokenParam = authStore.token ? `?token=${authStore.token}` : ''

    ws.value = new WebSocket(url + tokenParam)

    ws.value.onopen = () => {
      console.log('[GM WebSocket] 连接已建立')
      connectionStatus.value = 'connected'
      reconnectAttempts = 0 // 重置重连次数
    }

    ws.value.onclose = (event) => {
      console.log('[GM WebSocket] 连接已关闭', event.code, event.reason)
      connectionStatus.value = 'disconnected'
      ws.value = null
      pendingConfirm.value = null

      // 自动重连（非正常关闭时）
      // 1000 = 正常关闭，1001 = 页面离开
      if (event.code !== 1000 && event.code !== 1001) {
        scheduleReconnect()
      }
    }

    ws.value.onerror = (error) => {
      console.error('[GM WebSocket] 连接错误', error)
      connectionStatus.value = 'error'
      lastError.value = '连接失败'
      // onclose 会在 onerror 后触发，重连逻辑在 onclose 中处理
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

  // 计划重连
  function scheduleReconnect() {
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.warn('[GM WebSocket] 达到最大重连次数，停止重连')
      lastError.value = '连接失败，请手动重连'
      return
    }

    // 指数退避：1s, 2s, 4s, 8s, 16s
    const delay = RECONNECT_DELAY_BASE * Math.pow(2, reconnectAttempts)
    reconnectAttempts++

    console.log(`[GM WebSocket] 将在 ${delay}ms 后尝试第 ${reconnectAttempts} 次重连`)

    reconnectTimer = setTimeout(() => {
      console.log(`[GM WebSocket] 正在尝试第 ${reconnectAttempts} 次重连...`)
      connect()
    }, delay)
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
        streamingContent.value += data.content as string
        break

      case 'tool_call': {
        // AI 发起工具调用（流式通知）
        const toolName = data.tool_name as string
        const params = data.params as Record<string, unknown>
        const callId = data.call_id as string || `call_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

        currentRoundTools.value.push({
          id: callId,
          tool_name: toolName,
          params,
          status: 'executing',
          requires_confirmation: false, // 默认只读，后续可能被 confirm_actions 覆盖
        })
        console.log('[GM WebSocket] 工具调用通知:', toolName, callId)
        break
      }

      case 'tool_executing': {
        // 只读工具开始执行
        const toolName = data.tool_name as string
        const params = data.params as Record<string, unknown>
        const preview = data.preview as string | undefined
        const callId = data.call_id as string | undefined

        const existing = findTool(callId, toolName)
        if (existing) {
          existing.preview = preview
        } else {
          currentRoundTools.value.push({
            id: callId || `exec_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            tool_name: toolName,
            params,
            status: 'executing',
            requires_confirmation: false,
            preview,
          })
        }
        break
      }

      case 'tool_result': {
        // 只读工具执行完成
        const toolName = data.tool_name as string
        const callId = data.call_id as string | undefined
        const success = data.success as boolean
        const message = data.message as string

        const tool = findTool(callId, toolName)
        if (tool) {
          tool.status = success ? 'applied' : 'failed'
          tool.message = message
        }
        break
      }

      case 'confirm_actions': {
        // 请求用户确认修改操作
        const rawActions = data.actions as Array<{
          action_id: string
          tool_name: string
          params: Record<string, unknown>
          preview: string
          is_dangerous?: boolean
        }>
        const awaitingConfirmation = (data.awaiting_confirmation as boolean) ?? true

        // 转换为统一的 ToolExecution 格式，并去重
        const confirmTools: ToolExecution[] = []
        for (const a of rawActions) {
          // 检查是否已经在 currentRoundTools 中存在（通过 tool_call 事件添加的）
          const existingIndex = currentRoundTools.value.findIndex(
            t => t.tool_name === a.tool_name &&
                 JSON.stringify(t.params) === JSON.stringify(a.params) &&
                 !t.requires_confirmation  // 只匹配还未标记为需确认的
          )

          const toolExecution: ToolExecution = {
            id: a.action_id,
            action_id: a.action_id,  // 兼容字段
            tool_name: a.tool_name,
            params: a.params,
            status: 'pending' as ToolStatus,
            requires_confirmation: true,
            preview: a.preview,
            is_dangerous: a.is_dangerous,
          }

          if (existingIndex >= 0) {
            // 已存在，更新它而不是添加新的
            currentRoundTools.value[existingIndex] = toolExecution
          } else {
            // 不存在，添加到列表
            currentRoundTools.value.push(toolExecution)
          }

          confirmTools.push(toolExecution)
        }

        pendingConfirm.value = {
          tools: confirmTools,
          actions: confirmTools,  // 兼容字段
          awaitingConfirmation,
        }
        break
      }

      case 'tool_executed': {
        // 修改工具执行完成
        const actionId = data.action_id as string
        const success = data.success as boolean
        const message = data.message as string

        updateToolStatus(actionId, success ? 'success' : 'failed', message)
        console.log('[GM WebSocket] 工具已执行', data.tool_name, success)
        break
      }

      case 'done': {
        // 任务完成
        isLoading.value = false
        conversationId.value = data.conversation_id as string

        // 保存本轮消息（深拷贝避免响应式问题）
        if (streamingContent.value || currentRoundTools.value.length > 0) {
          const toolsCopy = currentRoundTools.value.length > 0
            ? JSON.parse(JSON.stringify(currentRoundTools.value))
            : undefined
          // 从工具中过滤出需要确认的操作作为 actions（兼容历史消息格式）
          const actionsCopy = toolsCopy?.filter((t: ToolExecution) => t.requires_confirmation)
          messages.value.push({
            role: 'assistant',
            content: streamingContent.value,
            tools: toolsCopy,
            actions: actionsCopy?.length > 0 ? actionsCopy : undefined,
            timestamp: Date.now(),
          })
        }

        if (data.tool_execution_summary) {
          executionStats.value = data.tool_execution_summary as ExecutionStats
        }

        // 重置状态
        streamingContent.value = ''
        currentRoundTools.value = []
        pendingConfirm.value = null
        break
      }

      case 'error':
        lastError.value = data.error as string
        if (!(data.recoverable as boolean)) {
          isLoading.value = false
        }
        break

      case 'pong':
      case 'round_start':
        // 忽略
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

  function sendUserMessage(
    message: string,
    options?: {
      images?: { base64: string; mime_type: string }[]
      enableWebSearch?: boolean
    }
  ) {
    if (!message.trim() && (!options?.images || options.images.length === 0)) return

    messages.value.push({
      role: 'user',
      content: message,
      images: options?.images,
      timestamp: Date.now(),
    })

    isLoading.value = true
    streamingContent.value = ''
    currentRoundTools.value = []
    lastError.value = null
    executionStats.value = null

    sendMessage({
      type: 'user_message',
      message,
      conversation_id: conversationId.value,
      images: options?.images,
      enable_web_search: options?.enableWebSearch,
    })
  }

  function sendConfirmResponse(approved: string[], rejected: string[] = []) {
    if (!pendingConfirm.value?.awaitingConfirmation) {
      console.warn('[GM WebSocket] 当前不需要发送确认响应')
      return false
    }

    // 更新状态
    updateToolStatuses(approved, rejected)

    // 保存当前轮内容
    if (streamingContent.value || currentRoundTools.value.length > 0) {
      // 深拷贝工具列表，避免后续清空影响已保存的消息
      const toolsCopy = currentRoundTools.value.length > 0
        ? JSON.parse(JSON.stringify(currentRoundTools.value))
        : undefined
      // 从工具中过滤出需要确认的操作作为 actions（兼容历史消息格式）
      const actionsCopy = toolsCopy?.filter((t: ToolExecution) => t.requires_confirmation)
      messages.value.push({
        role: 'assistant',
        content: streamingContent.value,
        tools: toolsCopy,
        actions: actionsCopy?.length > 0 ? actionsCopy : undefined,
        timestamp: Date.now(),
      })
    }

    // 重置流式状态
    streamingContent.value = ''
    currentRoundTools.value = []
    pendingConfirm.value = null
    isLoading.value = true

    const sent = sendMessage({
      type: 'confirm_response',
      approved,
      rejected,
    })

    if (sent) {
      console.log('[GM WebSocket] 发送确认响应', { approved, rejected })
    }
    return sent
  }

  // ==================== 便捷方法 ====================

  function approveAction(actionId: string) {
    updateToolStatus(actionId, 'approved')
  }

  function rejectAction(actionId: string) {
    updateToolStatus(actionId, 'rejected')
  }

  function markActionsApplied(actionIds: string[]) {
    for (const id of actionIds) {
      updateToolStatus(id, 'applied')
    }
  }

  function markActionsFailed(actionIds: string[]) {
    for (const id of actionIds) {
      updateToolStatus(id, 'failed')
    }
  }

  function confirmAll() {
    if (pendingConfirm.value) {
      const allIds = pendingConfirm.value.tools.map(t => t.id)
      updateToolStatuses(allIds, [])
    }
  }

  function rejectAll() {
    if (pendingConfirm.value) {
      const allIds = pendingConfirm.value.tools.map(t => t.id)
      updateToolStatuses([], allIds)
    }
  }

  function cancelTask() {
    sendMessage({ type: 'cancel' })
    isLoading.value = false
    pendingConfirm.value = null
  }

  function clearConversation() {
    messages.value = []
    conversationId.value = null
    streamingContent.value = ''
    currentRoundTools.value = []
    pendingConfirm.value = null
    lastError.value = null
    executionStats.value = null
  }

  function loadMessages(history: GMMessage[], convId?: string) {
    messages.value = history
    if (convId) {
      conversationId.value = convId
    }
  }

  function clearPendingConfirm() {
    pendingConfirm.value = null
  }

  // ==================== 兼容方法（向后兼容） ====================

  /** @deprecated 使用 updateToolStatuses 代替 */
  function confirmActions(approved: string[], rejected: string[] = []) {
    updateToolStatuses(approved, rejected)
  }

  /** @deprecated 使用 updateToolStatus 代替 */
  function updateActionStatusInMessages(actionId: string, status: ToolStatus) {
    updateToolStatus(actionId, status)
  }

  /** @deprecated 使用 updateToolStatuses 代替 */
  function updateActionStatuses(approved: string[], rejected: string[]) {
    updateToolStatuses(approved, rejected)
  }

  // ==================== 生命周期 ====================

  onUnmounted(() => {
    // 清理重连定时器
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
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
    executingTools,           // 兼容：映射到 currentRoundTools
    currentRoundTools,        // 新：统一的工具列表
    pendingConfirm,
    hasUnconfirmedActions,
    executionStats,

    // 兼容：currentRoundActions 仅包含需要确认的工具
    currentRoundActions,

    // 方法
    connect,
    disconnect,
    reconnect,
    sendUserMessage,
    sendConfirmResponse,
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
    updateToolStatus,         // 新：统一状态更新
    updateToolStatuses,       // 新：批量状态更新

    // 兼容方法（逐步废弃）
    confirmActions,
    updateActionStatusInMessages,
    updateActionStatuses,
  }
}
