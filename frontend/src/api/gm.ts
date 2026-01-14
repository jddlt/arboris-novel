/**
 * GM Agent API 客户端
 * 提供与 GM Agent 操作管理的接口
 * 注：对话功能已迁移至 WebSocket (useGMWebSocket.ts)
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
  timestamp?: string
  actions?: {
    action_id: string
    tool_name: string
    params: Record<string, unknown>
    preview?: string
    status: string
  }[]
  executed_tools?: {
    tool_name: string
    params?: Record<string, unknown>
    status: string
    message?: string
    preview?: string
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

/** 图片数据（用于 API 请求） */
export interface ImagePayload {
  base64: string
  mime_type: string
}

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

/**
 * 截断对话消息（回溯功能）
 * @param projectId 项目 ID
 * @param conversationId 对话 ID
 * @param keepCount 保留的消息数量（从开头算起）
 * @returns 被删除的消息数量
 */
export async function truncateConversation(
  projectId: string,
  conversationId: string,
  keepCount: number
): Promise<{ deleted_count: number }> {
  const response = await fetch(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/gm/conversations/${conversationId}/truncate`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ keep_count: keepCount }),
    }
  )
  return handleResponse(response)
}
