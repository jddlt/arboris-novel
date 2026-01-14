/**
 * 作者备忘录和角色状态 API 客户端
 */

import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import { API_BASE_URL, API_PREFIX } from './novel'

// ==================== 类型定义 ====================

/** 备忘录类型 */
export type AuthorNoteType =
  | 'chapter'           // 章节备忘
  | 'character_secret'  // 角色秘密
  | 'style'             // 写作风格
  | 'todo'              // 待办事项
  | 'global'            // 全局备忘
  | 'plot_thread'       // 剧情线索
  | 'timeline'          // 时间线
  | 'item'              // 物品/道具
  | 'location'          // 地点场景
  | 'ability'           // 技能/能力
  | 'revision'          // 待修改
  | 'world_building'    // 世界观补充

/** 备忘录 */
export interface AuthorNote {
  id: number
  project_id: string
  type: AuthorNoteType
  title: string
  content: string
  chapter_number?: number | null
  volume_id?: number | null
  volume_title?: string | null
  character_id?: number | null
  is_active: boolean
  priority: number
  created_at: string
  updated_at: string
}

/** 创建备忘录请求 */
export interface CreateNoteRequest {
  type: AuthorNoteType
  title: string
  content: string
  chapter_number?: number
  volume_id?: number
  character_id?: number
  priority?: number
}

/** 更新备忘录请求 */
export interface UpdateNoteRequest {
  title?: string
  content?: string
  priority?: number
  is_active?: boolean
  volume_id?: number | null
  chapter_number?: number | null
}

/** 备忘录列表响应 */
export interface NoteListResponse {
  notes: AuthorNote[]
  total: number
}

/** 角色状态 */
export interface CharacterState {
  id: number
  character_id: number
  chapter_number: number
  data: Record<string, unknown>
  change_note?: string | null
  created_at: string
  character_name?: string
}

/** 创建/更新角色状态请求 */
export interface UpsertStateRequest {
  character_id: number
  chapter_number: number
  data: Record<string, unknown>
  change_note?: string
}

/** 角色状态列表响应 */
export interface StateListResponse {
  states: CharacterState[]
}

/** 可选择的备忘录（用于生成弹窗） */
export interface SelectableNote {
  id: number
  type: AuthorNoteType
  title: string
  content: string
  chapter_number?: number | null
  character_name?: string | null
  is_recommended: boolean
}

/** 可选择的角色状态（用于生成弹窗） */
export interface SelectableState {
  id: number
  character_id: number
  character_name: string
  chapter_number: number
  data: Record<string, unknown>
  summary: string
}

/** 生成上下文选项 */
export interface GenerationContextOptions {
  notes: SelectableNote[]
  states: SelectableState[]
  recommended_note_ids: number[]
  recommended_state_ids: number[]
}

/** 状态模板 */
export interface StateTemplate {
  id: number
  name: string
  display_name: string
  description?: string | null
  schema: Record<string, unknown>
  is_system: boolean
  created_at: string
}

// ==================== 通用请求函数 ====================

const request = async <T>(url: string, options: RequestInit = {}): Promise<T> => {
  const authStore = useAuthStore()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers
  })

  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }

  const response = await fetch(url, { ...options, headers })

  if (response.status === 401) {
    authStore.logout()
    router.push('/login')
    throw new Error('会话已过期，请重新登录')
  }

  if (response.status === 204) {
    return null as T
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `请求失败，状态码: ${response.status}`)
  }

  return response.json()
}

// ==================== 备忘录 API ====================

/**
 * 获取项目的备忘录列表
 */
export async function listNotes(
  projectId: string,
  noteType?: AuthorNoteType,
  activeOnly: boolean = true
): Promise<NoteListResponse> {
  const params = new URLSearchParams()
  if (noteType) params.set('note_type', noteType)
  params.set('active_only', String(activeOnly))

  return request<NoteListResponse>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/notes?${params}`
  )
}

/**
 * 创建备忘录
 */
export async function createNote(
  projectId: string,
  data: CreateNoteRequest
): Promise<AuthorNote> {
  return request<AuthorNote>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/notes`,
    {
      method: 'POST',
      body: JSON.stringify(data)
    }
  )
}

/**
 * 更新备忘录
 */
export async function updateNote(
  projectId: string,
  noteId: number,
  data: UpdateNoteRequest
): Promise<AuthorNote> {
  return request<AuthorNote>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/notes/${noteId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(data)
    }
  )
}

/**
 * 删除备忘录
 */
export async function deleteNote(projectId: string, noteId: number): Promise<void> {
  return request<void>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/notes/${noteId}`,
    { method: 'DELETE' }
  )
}

/**
 * 批量删除备忘录
 */
export async function batchDeleteNotes(projectId: string, ids: number[]): Promise<void> {
  return request<void>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/notes/batch-delete`,
    {
      method: 'POST',
      body: JSON.stringify({ ids })
    }
  )
}

/**
 * 批量更新备忘录激活状态
 */
export async function batchUpdateActive(
  projectId: string,
  ids: number[],
  isActive: boolean
): Promise<{ updated: number }> {
  return request<{ updated: number }>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/notes/batch-update-active`,
    {
      method: 'POST',
      body: JSON.stringify({ ids, is_active: isActive })
    }
  )
}

// ==================== 角色状态 API ====================

/**
 * 获取项目中所有角色的最新状态
 */
export async function listStates(
  projectId: string,
  chapterNumber?: number
): Promise<StateListResponse> {
  const params = new URLSearchParams()
  if (chapterNumber !== undefined) {
    params.set('chapter_number', String(chapterNumber))
  }

  return request<StateListResponse>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/states?${params}`
  )
}

/**
 * 获取指定角色的状态历史
 */
export async function listCharacterStates(
  projectId: string,
  characterId: number
): Promise<CharacterState[]> {
  return request<CharacterState[]>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/states/character/${characterId}`
  )
}

/**
 * 创建或更新角色状态
 */
export async function upsertState(
  projectId: string,
  data: UpsertStateRequest
): Promise<CharacterState> {
  return request<CharacterState>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/states`,
    {
      method: 'POST',
      body: JSON.stringify(data)
    }
  )
}

/**
 * 更新角色状态
 */
export async function updateState(
  projectId: string,
  stateId: number,
  data: { data?: Record<string, unknown>; change_note?: string }
): Promise<CharacterState> {
  return request<CharacterState>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/states/${stateId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(data)
    }
  )
}

/**
 * 删除角色状态
 */
export async function deleteState(projectId: string, stateId: number): Promise<void> {
  return request<void>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/states/${stateId}`,
    { method: 'DELETE' }
  )
}

// ==================== 生成上下文 API ====================

/**
 * 获取生成章节时可选择的上下文
 */
export async function getGenerationContextOptions(
  projectId: string,
  chapterNumber: number
): Promise<GenerationContextOptions> {
  return request<GenerationContextOptions>(
    `${API_BASE_URL}${API_PREFIX}/novels/${projectId}/generation-context/options?chapter_number=${chapterNumber}`
  )
}

// ==================== 状态模板 API ====================

/**
 * 获取所有状态模板
 */
export async function listTemplates(): Promise<{ templates: StateTemplate[] }> {
  return request<{ templates: StateTemplate[] }>(
    `${API_BASE_URL}${API_PREFIX}/state-templates`
  )
}
