/**
 * GM Agent Panel 状态管理
 * 管理 AI 助手面板的开关状态，支持 localStorage 持久化
 */

import { defineStore } from 'pinia'

const STORAGE_KEY = 'gm_panel_state'

interface GMPanelState {
  /** 各项目的面板开关状态 */
  projectPanelOpen: Record<string, boolean>
  /** 当前活动的项目 ID */
  activeProjectId: string | null
}

function loadFromStorage(): Partial<GMPanelState> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      return JSON.parse(stored)
    }
  } catch (e) {
    console.error('Failed to load GM panel state from localStorage:', e)
  }
  return {}
}

function saveToStorage(state: GMPanelState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      projectPanelOpen: state.projectPanelOpen,
      activeProjectId: state.activeProjectId,
    }))
  } catch (e) {
    console.error('Failed to save GM panel state to localStorage:', e)
  }
}

export const useGMPanelStore = defineStore('gmPanel', {
  state: (): GMPanelState => {
    const stored = loadFromStorage()
    return {
      projectPanelOpen: stored.projectPanelOpen || {},
      activeProjectId: stored.activeProjectId || null,
    }
  },

  getters: {
    /** 当前项目的面板是否打开 */
    isPanelOpen: (state) => {
      if (!state.activeProjectId) return false
      return state.projectPanelOpen[state.activeProjectId] ?? false
    },
  },

  actions: {
    /** 设置当前活动项目 */
    setActiveProject(projectId: string) {
      this.activeProjectId = projectId
      saveToStorage(this.$state)
    },

    /** 打开面板 */
    openPanel() {
      if (this.activeProjectId) {
        this.projectPanelOpen[this.activeProjectId] = true
        saveToStorage(this.$state)
      }
    },

    /** 关闭面板 */
    closePanel() {
      if (this.activeProjectId) {
        this.projectPanelOpen[this.activeProjectId] = false
        saveToStorage(this.$state)
      }
    },

    /** 切换面板状态 */
    togglePanel() {
      if (this.activeProjectId) {
        const current = this.projectPanelOpen[this.activeProjectId] ?? false
        this.projectPanelOpen[this.activeProjectId] = !current
        saveToStorage(this.$state)
      }
    },

    /** 清除项目的面板状态 */
    clearProject(projectId: string) {
      delete this.projectPanelOpen[projectId]
      if (this.activeProjectId === projectId) {
        this.activeProjectId = null
      }
      saveToStorage(this.$state)
    },
  },
})
