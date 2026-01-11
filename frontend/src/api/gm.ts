/**
 * GM Agent API 客户端
 * 提供与 GM Agent 对话、操作管理的接口
 */

import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import { API_BASE_URL, API_PREFIX } from './novel'

// ==================== 类型定义 ====================

/** 待执行操作 */
export interface GMPendingAction {
  action_id: string
  tool_name: string
  params: Record<string, unknown>
  preview: string
  status: 'pending' | 'applied' | 'discarded' | 'failed'
}

/** GM 对话响应 */
export interface GMChatResponse {
  conversation_id: string
  message: string
  pending_actions: GMPendingAction[]
}

/** 操作执行结果 */
export interface ActionResult {
  action_id: string
  success: boolean
  message: string
  data?: Record<string, unknown>
}

/** 应用操作响应 */
export interface ApplyActionsResponse {
  applied: string[]
  results: ActionResult[]
}

/** 对话摘要 */
export interface ConversationSummary {
  id: string
  title: string
  message_count: number
  is_archived: boolean
  created_at: string
  updated_at: string
}

/** 对话消息 */
export interface ConversationMessage {
  role: 'user' | 'assistant'
  content: string
  actions?: {
    action_id: string
    tool_name: string
    preview: string
    status: string
  }[]
}

/** 对话详情 */
export interface ConversationDetail {
  id: string
  project_id: string
  title: string
  messages: ConversationMessage[]
  is_archived: boolean
  created_at: string
  updated_at: string
}

/** SSE 事件类型 */
export type GMStreamEvent =
  | { type: 'start'; conversation_id: string }
  | { type: 'content'; content: string }
  | { type: 'pending_actions'; actions: GMPendingAction[] }
  | { type: 'done'; conversation_id: string; message: string }
  | { type: 'error'; error: string }

// ==================== 请求工具函数 ====================

const getAuthHeaders = (): HeadersInit => {
  const authStore = useAuthStore()
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }
  if (authStore.isAuthenticated && authStore.token) {
    headers['Authorization'] = `Bearer ${authStore.token}`
  }
  return headers
}

const handleResponse = async (response: Response) => {
  if (response.status === 401) {
    const authStore = useAuthStore()
    authStore.logout()
    router.push('/login')
    throw new Error('会话已过期，请重新登录')
  }
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `请求失败，状态码: ${response.status}`)
  }
  return response.json()
}

// ==================== API 函数 ====================

/**
 * 与 GM Agent 对话（普通模式）
 */
export async function chatWithGM(
  projectId: string,
  message: string,
  options?: {
    conversationId?: string
    enableWebSearch?: boolean
  }
): Promise<GMChatResponse> {
  const response = await fetch(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/gm/chat`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        message,
        conversation_id: options?.conversationId,
        enable_web_search: options?.enableWebSearch ?? false,
      }),
    }
  )
  return handleResponse(response)
}

/**
 * 与 GM Agent 流式对话（SSE）
 * @returns AsyncGenerator 产生 SSE 事件
 */
export async function* streamChatWithGM(
  projectId: string,
  message: string,
  options?: {
    conversationId?: string
    enableWebSearch?: boolean
  }
): AsyncGenerator<GMStreamEvent> {
  const authStore = useAuthStore()

  const response = await fetch(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/gm/chat/stream`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        message,
        conversation_id: options?.conversationId,
        enable_web_search: options?.enableWebSearch ?? false,
      }),
    }
  )

  if (response.status === 401) {
    authStore.logout()
    router.push('/login')
    throw new Error('会话已过期，请重新登录')
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `请求失败，状态码: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('无法获取响应流')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            yield data as GMStreamEvent
          } catch {
            // 忽略解析错误
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/**
 * 应用待执行操作
 */
export async function applyActions(
  projectId: string,
  actionIds: string[]
): Promise<ApplyActionsResponse> {
  const response = await fetch(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/gm/apply`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ action_ids: actionIds }),
    }
  )
  return handleResponse(response)
}

/**
 * 放弃待执行操作
 */
export async function discardActions(
  projectId: string,
  actionIds: string[]
): Promise<{ discarded_count: number }> {
  const response = await fetch(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/gm/discard`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ action_ids: actionIds }),
    }
  )
  return handleResponse(response)
}

/**
 * 获取对话列表
 */
export async function getConversations(
  projectId: string,
  includeArchived = false
): Promise<ConversationSummary[]> {
  let url = `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/gm/conversations`
  if (includeArchived) {
    url += '?include_archived=true'
  }
  const response = await fetch(url, {
    headers: getAuthHeaders(),
  })
  return handleResponse(response)
}

/**
 * 获取对话详情
 */
export async function getConversationDetail(
  projectId: string,
  conversationId: string
): Promise<ConversationDetail> {
  const response = await fetch(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/gm/conversations/${conversationId}`,
    {
      headers: getAuthHeaders(),
    }
  )
  return handleResponse(response)
}

/**
 * 归档对话
 */
export async function archiveConversation(
  projectId: string,
  conversationId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/gm/conversations/${conversationId}`,
    {
      method: 'DELETE',
      headers: getAuthHeaders(),
    }
  )
  if (response.status === 401) {
    const authStore = useAuthStore()
    authStore.logout()
    router.push('/login')
    throw new Error('会话已过期，请重新登录')
  }
  if (!response.ok && response.status !== 204) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `请求失败，状态码: ${response.status}`)
  }
}
